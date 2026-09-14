#!/usr/bin/env python3
"""Validate D01-44 native measurement evidence without inventing a performance target.

Wall-clock end-frame samples are the FPS denominator. Simulation, thread, GPU,
transition and screenshot costs retain separate labels; no bad frame is trimmed.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

from PIL import Image, ImageStat

from verify_d01_039 import numeric, require, strict_object
from verify_d01_043 import warnings


PROJECT = Path(__file__).resolve().parents[1]
BASELINE_LOG = PROJECT / "Build/Demo01/D01-043-runs/20260905T090626.266544Z/soak.stdout.log"
ARTIFACT_ROOT = Path("/root/biella/artifacts/games/D01-044")


FRAME_FIELDS = ("frame,wall_seconds,wall_delta_ms,sim_delta_ms,stage,phase,cycle,game_ms,render_ms,"
                "rhi_ms,gpu_ms,game_wait_ms,render_wait_ms,swap_ms,pawn_count,autonomous_pawns,"
                "player_x,player_y,player_z,view_yaw,health,ammo,pressure,active_audio,active_vfx").split(",")
INTEGER_FIELDS = ("frame", "cycle", "pawn_count", "autonomous_pawns", "ammo", "active_audio", "active_vfx")
TIMING_FIELDS = ("game_ms", "render_ms", "rhi_ms", "gpu_ms", "game_wait_ms", "render_wait_ms", "swap_ms")


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=strict_object)


def identity(path):
    path = Path(path)
    return {"path": str(path), "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def integer(value, label, minimum=0):
    require(not isinstance(value, bool), f"Invalid boolean integer {label}")
    result = numeric(value, label)
    require(result.is_integer() and result >= minimum, f"Invalid integer {label}")
    return int(result)


def close(a, b, label, tolerance=.002):
    require(abs(a - b) <= tolerance, f"{label}: {a} differs from {b}")


def percentile(values, percentile_value):
    position = (len(values) - 1) * percentile_value / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def frame_statistics(values):
    if not values:
        return {"count": 0, "availability": "NO_SAMPLES"}
    ordered = sorted(values)
    total = sum(ordered)
    return {"count": len(values), "duration_seconds": total / 1000, "mean_ms": total / len(values),
            **{f"p{p}_ms": percentile(ordered, p) for p in (50, 90, 95, 99)},
            "max_ms": ordered[-1], "min_ms": ordered[0],
            "observed_fps": len(values) * 1000 / total if total > 0 else None,
            "hitches_gt_ms": {str(threshold): sum(v > threshold for v in values) for threshold in (33.3, 50, 100)}}


def native_settings(settings, width, height):
    require(isinstance(settings, dict), "Missing settings snapshot")
    require(settings.get("rhi") == "Vulkan", "Native rendering requires Vulkan")
    require(settings.get("viewport_width") == width and settings.get("viewport_height") == height,
            "Native viewport dimensions differ from requested resolution")
    for name in ("fixed_timestep", "benchmarking", "smooth_framerate", "use_fixed_framerate"):
        require(settings.get(name) is False, f"Native measurement requires {name}=false")
    cvars = settings.get("cvars", {})
    for key, value in (("r.VSync", 0), ("t.MaxFPS", 0), ("r.ScreenPercentage", 100),
                       ("r.DynamicRes.OperationMode", 0)):
        require(key in cvars and numeric(cvars[key], key) == value, f"Native measurement requires {key}={value}")
    for key in ("r.NGX.DLSS.Enable", "r.Streamline.DLSSG.Enable", "r.FidelityFX.FI.Enabled"):
        require(key in cvars and (cvars[key] == "unavailable" or numeric(cvars[key], key) == 0),
                f"Native measurement requires disabled/unavailable {key}")


def read_frames(path):
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == FRAME_FIELDS, "Unexpected/missing/duplicate frame CSV columns")
        frames = []
        for raw in reader:
            require(None not in raw and None not in raw.values(), "Malformed frame CSV row")
            row = {key: value if key in ("phase", "stage") else numeric(value, key) for key, value in raw.items()}
            for key in INTEGER_FIELDS:
                row[key] = integer(row[key], key)
            require(row["frame"] > 0, "Invalid initial frame sequence")
            require(row["stage"] in ("warmup", "measure", "capture"), "Unknown frame stage")
            require(row["phase"] in ("active", "terminal", "travel"), "Unknown gameplay phase")
            require(row["wall_seconds"] > 0 and row["wall_delta_ms"] > 0 and row["sim_delta_ms"] >= 0,
                    "Invalid frame clocks")
            require(all(row[key] >= 0 for key in TIMING_FIELDS), "Negative thread/GPU timing")
            require(0 <= row["health"] <= 100 and row["ammo"] >= 0, "Invalid health/ammo")
            require(row["active_audio"] <= 14 and row["active_vfx"] <= 24, "Feedback component cap exceeded")
            require(0 <= row["autonomous_pawns"] <= row["pawn_count"], "Invalid autonomous pawn count")
            if row["phase"] != "travel":
                require(row["pawn_count"] == 4, "Gameplay pawn membership differs from authored encounter")
            if frames:
                require(row["frame"] == frames[-1]["frame"] + 1, "Broken frame sequence")
            previous_wall = frames[-1]["wall_seconds"] if frames else 0
            close(row["wall_delta_ms"], (row["wall_seconds"] - previous_wall) * 1000,
                  "Frame wall delta mismatch", tolerance=.01)
            if frames:
                previous = frames[-1]
                require(row["cycle"] in (previous["cycle"], previous["cycle"] + 1), "Cycle regressed/skipped")
                rank = {"warmup": 0, "measure": 1, "capture": 2}
                require(rank[row["stage"]] >= rank[previous["stage"]], "Frame stage order regressed")
            frames.append(row)
    require(frames, "Empty frame capture")
    return frames


def telemetry(path, perf):
    events = [json.loads(line, object_pairs_hook=strict_object) for line in Path(path).read_text().splitlines()]
    require(events, "Empty telemetry")
    session = events[0].get("session")
    for index, event in enumerate(events):
        require(event.get("schema") == "biella.demo01.telemetry/v1", "Wrong telemetry schema")
        require(session and event.get("session") == session, "Telemetry session changed")
        require(type(event.get("seq")) is int and event["seq"] == index + 1, "Broken telemetry sequence")
        require(type(event.get("restart_count")) is int and event["restart_count"] >= 0, "Invalid restart count")
        require(isinstance(event.get("fields"), dict) and all(isinstance(k, str) and isinstance(v, str)
                for k, v in event["fields"].items()), "Malformed telemetry fields")
        require(event.get("map") and event.get("event"), "Missing telemetry map/event")
        require(numeric(event["wall_seconds"], "telemetry wall") >= 0 and
                numeric(event["sim_seconds"], "telemetry sim") >= 0, "Invalid telemetry clocks")
        require(event["event"] not in ("scenario_failed", "perf_failed"), "Runtime failure marker")
        if index:
            previous = events[index - 1]
            require(event["wall_seconds"] >= previous["wall_seconds"], "Telemetry wall clock regressed")
            require(previous["restart_count"] <= event["restart_count"] <= previous["restart_count"] + 1,
                    "Telemetry restart counter regressed/skipped")
    require(events[0]["event"] == "telemetry_ready" and events[-1]["event"] == "telemetry_shutdown",
            "Incomplete telemetry lifecycle")
    counts = Counter(e["event"] for e in events)
    for name in ("telemetry_ready", "telemetry_shutdown", "perf_begin", "perf_measure_begin", "perf_complete"):
        require(counts[name] == 1, f"Expected one {name}")
    begin, measure, complete = [next(e for e in events if e["event"] == name)
                                for name in ("perf_begin", "perf_measure_begin", "perf_complete")]
    require(begin["seq"] < measure["seq"] < complete["seq"], "Misordered performance lifecycle")
    require(counts["perf_heartbeat"] > 0, "Missing live performance heartbeat")
    heartbeats = [e for e in events if e["event"] == "perf_heartbeat"]
    counters = [integer(e["fields"]["frame"], "heartbeat frame") for e in heartbeats]
    require(all(b > a for a, b in zip(counters, counters[1:])), "Heartbeat frame progress stalled")
    # perf_complete is after the final screenshot. Bound gameplay corroboration
    # by actual raw measurement clocks so capture-stage activity cannot pass it.
    origin = numeric(begin["wall_seconds"], "begin wall") - numeric(begin["fields"]["perf_wall_seconds"], "begin perf wall")
    for event in (measure, complete):
        close(event["wall_seconds"] - numeric(event["fields"]["perf_wall_seconds"], "perf wall"),
              origin, "Telemetry/performance clock origin differs", tolerance=.01)
    lower = origin + numeric(perf["measure_start_wall_seconds"], "measure start")
    upper = origin + numeric(perf["measure_end_wall_seconds"], "measure end")
    workload = [e for e in events if lower <= e["wall_seconds"] <= upper]
    damage = [e for e in workload if e["event"] == "damage" and numeric(e["fields"].get("amount"), "damage") > 0]
    shots = [e for e in workload if e["event"] == "weapon_fire" and numeric(e["fields"].get("damage"), "shot damage") > 0]
    require(damage, "No live positive damage during measured gameplay")
    require(shots, "No measured weapon_fire corroborates consumed player ammo")
    restarts = [e for e in events[begin["seq"]:complete["seq"]] if e["event"] == "restart_requested"]
    require(restarts and len(restarts) == integer(perf["restarts"], "restarts", 1), "Missing/mismatched natural restart evidence")
    require(counts["perf_restart"] == len(restarts), "Performance restart marker mismatch")
    require(complete["restart_count"] - begin["restart_count"] == len(restarts), "Restart lifecycle count mismatch")
    cycles = [e for e in events if e["event"] == "perf_cycle_begin"]
    require(len(cycles) == integer(perf["cycles"], "cycles"), "Cycle telemetry count differs")
    require([integer(e["fields"]["cycle"], "cycle") for e in cycles] == list(range(1, len(cycles) + 1)),
            "Cycle telemetry sequence differs")
    return {"session": session, "records": len(events), "event_counts": dict(counts),
            "measured_positive_damage_events": len(damage), "measured_player_shot_events": len(shots),
            "measured_wall_begin": measure["wall_seconds"], "complete_wall_seconds": complete["wall_seconds"],
            "restart_events": len(restarts), "sha256": identity(path)["sha256"],
            "cycle_begin_perf_seconds": {e["fields"]["cycle"]: numeric(e["fields"]["perf_wall_seconds"], "cycle wall") for e in cycles},
            "restart_perf_seconds": [numeric(e["fields"]["perf_wall_seconds"], "restart wall")
                                     for e in events if e["event"] == "perf_restart"]}


def captures(directory, names, width, height):
    require(isinstance(names, list) and len(names) >= 2 and len(names) == len(set(names)),
            "Expected distinct warmup and final capture files")
    result = []
    for name in names:
        require(isinstance(name, str) and name, "Invalid capture path")
        path = (directory / name).resolve()
        require(path.is_relative_to(directory.resolve()) or
                path.is_relative_to((ARTIFACT_ROOT / directory.name).resolve()),
                "Unsafe capture path outside run and its designated artifact directory")
        with Image.open(path) as image:
            require(image.format == "PNG", "Capture is not PNG")
            image.load()  # A plausible PNG header is insufficient.
            require(image.size == (width, height), "Capture dimensions differ from native viewport")
            rgb = image.convert("RGB")
            deviation = ImageStat.Stat(rgb).stddev
            require(max(deviation) > 0, "Decoded capture is blank/uniform")
            result.append({**identity(path), "width": image.width, "height": image.height,
                           "rgb_stddev": deviation, "status": "GENERATED_DRAFT"})
    return result


def verify_log(content, baseline):
    require("**** TEST COMPLETE. EXIT CODE: 0 ****" in content, "Unreal completion missing")
    require(re.search(r"Result=\{Success\}.*Name=\{NativePerformance\}", content), "NativePerformance automation success missing")
    require("D01_044_TEST COMPLETE" in content, "NativePerformance scenario completion missing")
    require(not re.search(r"Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:|"
                          r"Log\w+: Error:|VK_ERROR_DEVICE_LOST|D01_TELEMETRY_ERROR|D01_044_TEST FAIL", content),
            "Runtime error, crash, ensure, device loss or write failure")
    observed, prior = warnings(content), warnings(baseline)
    unexpected = sorted(observed.keys() - prior.keys())
    require(not unexpected, f"New warning signatures require investigation: {unexpected}")
    return {"warnings": dict(observed), "baseline_warnings": dict(prior),
            "classification": "Exact predecessor warning signatures remain disclosed; not warning-free."}


def verify_run(directory, seconds, width, height, warmup, log_verifier=verify_log):
    directory = Path(directory)
    require(numeric(seconds, "requested seconds") > 0 and numeric(warmup, "requested warmup") >= 0,
            "Invalid requested duration")
    perf = read_json(directory / "perf.json")
    require(perf.get("schema") == "biella.demo01.native_performance/v1" and perf.get("result") == "PASS",
            "Incomplete native performance result")
    close(numeric(perf["requested_seconds"], "requested_seconds"), seconds, "Requested duration mismatch")
    close(numeric(perf["warmup_seconds"], "warmup_seconds"), warmup, "Warmup duration mismatch")
    require(integer(perf["process_id"], "process_id", 1) > 0, "Missing process identity")
    require(numeric(perf["platform_seconds_start"], "platform_seconds_start") > 0, "Missing platform clock origin")
    require(datetime.fromisoformat(perf["utc_start"].replace("Z", "+00:00")).tzinfo, "UTC start requires timezone")
    for name in ("settings_begin", "settings"):
        native_settings(perf.get(name), width, height)
    require(perf["settings_begin"]["cvars"] == perf["settings"]["cvars"],
            "Native rendering settings changed between beginning and end")
    frames = read_frames(directory / "frames.csv")
    measured = [f for f in frames if f["stage"] == "measure"]
    warm = [f for f in frames if f["stage"] == "warmup"]
    captured = [f for f in frames if f["stage"] == "capture"]
    require(warm and measured and captured, "Missing warmup/measurement/capture samples")
    require(len(frames) == integer(perf["frame_rows"], "frame_rows") and
            len(measured) == integer(perf["measured_rows"], "measured_rows"), "Frame row totals differ")
    duration = sum(f["wall_delta_ms"] for f in measured) / 1000
    close(duration, numeric(perf["measured_seconds"], "measured_seconds"), "Reported measured duration differs")
    require(duration + .002 >= seconds, "Insufficient measured duration")
    require(measured[0]["wall_seconds"] + .002 >= warmup, "Insufficient warmup duration")
    close(numeric(perf["measure_start_wall_seconds"], "measure start"),
          measured[0]["wall_seconds"] - measured[0]["wall_delta_ms"] / 1000, "Measurement start differs")
    close(numeric(perf["measure_end_wall_seconds"], "measure end"),
          measured[-1]["wall_seconds"], "Measurement end differs")
    active = [f for f in measured if f["phase"] == "active"]
    require(len(active) >= 2, "No live active gameplay samples")
    require(any(f["autonomous_pawns"] > 0 for f in active), "No enabled autonomous gameplay actors")
    movement = sum(math.dist([a[k] for k in ("player_x", "player_y", "player_z")],
                             [b[k] for k in ("player_x", "player_y", "player_z")])
                   for a, b in zip(measured, measured[1:])
                   if a["cycle"] == b["cycle"] and a["phase"] == b["phase"] == "active")
    require(movement > 0 and numeric(perf["movement_distance"], "movement_distance") > 0,
            "No real player movement in measured active frames")
    require(numeric(perf["ai_movement_distance"], "ai_movement_distance") > 0, "No autonomous movement measured")
    require(integer(perf["shots_consumed"], "shots_consumed", 1) > 0, "No real ammo consumed")
    require(type(perf["damage_observed"]) in (int, float) and numeric(perf["damage_observed"], "damage_observed") > 0,
            "No real damage observed")
    require(integer(perf["cycles"], "cycles", 2) >= 2, "No restarted encounter cycle")
    require(integer(perf["terminal_frames"], "terminal_frames", 1) > 0 and
            any(f["phase"] == "terminal" for f in measured), "No terminal gameplay frames measured")
    require(perf["terminal_frames"] == sum(f["phase"] == "terminal" for f in measured), "Terminal frame count differs")
    timeline = telemetry(directory / "telemetry.jsonl", perf)
    previous = {frame["frame"]: frames[index - 1] if index else None for index, frame in enumerate(frames)}
    transition = lambda frame: frame["phase"] == "travel" or bool(previous[frame["frame"]] and
        (previous[frame["frame"]]["phase"] == "travel" or previous[frame["frame"]]["cycle"] != frame["cycle"]))
    def hitch_context(frame):
        prior = previous[frame["frame"]]
        restarts = [wall for wall in timeline["restart_perf_seconds"] if wall <= frame["wall_seconds"]]
        start = timeline["cycle_begin_perf_seconds"].get(str(frame["cycle"]))
        return {**frame, "previous_phase": prior["phase"] if prior else None,
                "previous_cycle": prior["cycle"] if prior else None, "transition_interval": transition(frame),
                "seconds_since_cycle_start": frame["wall_seconds"] - start if start is not None else None,
                "seconds_since_preceding_restart": frame["wall_seconds"] - max(restarts) if restarts else None}
    groups = {"all_measurement": measured, "active": active,
              "terminal": [f for f in measured if f["phase"] == "terminal"],
              "travel": [f for f in measured if f["phase"] == "travel"], "warmup": warm, "capture": captured,
              "transition_intervals": [f for f in measured if transition(f)]}
    timings = {}
    for key in TIMING_FIELDS:
        samples = [f[key] for f in measured if f[key] > 0]
        if key in ("gpu_ms", "game_ms", "render_ms"):
            require(samples, f"No available native {key} timing evidence")
        stats = frame_statistics(samples)
        # A timer can be unavailable/zero, and timer sums are not elapsed runtime.
        stats.pop("observed_fps", None)
        stats.pop("duration_seconds", None)
        stats["zero_or_unavailable_samples"] = len(measured) - len(samples)
        stats["interpretation"] = "Positive engine timer samples; may be pipelined/delayed; not FPS or additive frame cost."
        timings[key] = stats
    log_report = log_verifier((directory / "runtime.stdout.log").read_text(errors="replace"), BASELINE_LOG.read_text())
    return {"result": "PASS", "logs": log_report, "scope": "Observed native development-host workload; no shipping target or performance budget accepted.",
            "settings": perf["settings"], "measurement_start_wall_seconds": measured[0]["wall_seconds"] - measured[0]["wall_delta_ms"] / 1000,
            "measurement_end_wall_seconds": measured[-1]["wall_seconds"],
            "frame_time": {name: frame_statistics([f["wall_delta_ms"] for f in rows]) for name, rows in groups.items()},
            "simulation_delta": {k: v for k, v in frame_statistics([f["sim_delta_ms"] for f in measured]).items()
                                 if k != "observed_fps"},
            "thread_timings": timings, "player_movement_from_measured_frames": movement,
            "top_hitches": [hitch_context(f) for f in sorted(measured, key=lambda f: f["wall_delta_ms"], reverse=True)[:10]],
            "phase_grouping": "Active/terminal/travel are end-of-frame state. Transition intervals overlap those groups and include either endpoint in travel or a cycle change; reload stalls may end in active. No measured interval is omitted.",
            "percentile_method": "Linear interpolation at (n-1)*p/100; every measured frame retained, including transitions.",
            "telemetry": timeline, "captures": captures(directory, perf["capture_files"], width, height),
            "raw": {name: identity(directory / name) for name in ("frames.csv", "perf.json", "telemetry.jsonl")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--warmup", type=float, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_run(args.directory, args.seconds, args.width, args.height, args.warmup), indent=2))
