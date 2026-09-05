#!/usr/bin/env python3
"""Check live D02-01 evidence; report measured host behavior without an FPS target."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageStat


FIELDS = ("frame,wall_seconds,wall_delta_ms,sim_delta_ms,phase,x,y,z,visible_cells,"
          "loaded_cells,used_physical_bytes,health,ammo,pressure,safety_holds").split(",")
CAPTURES = ("street_start", "interior", "terrace", "distant_region", "injury_return", "final_return")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(path):
    return {"path": str(path), "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def verify(directory):
    directory = Path(directory).resolve()
    report = json.loads((directory / "streaming.json").read_text())
    require(report.get("schema") == "biella.games.world_streaming/v1", "Unexpected evidence schema")
    require(report.get("result") == "PASS" and not report.get("error"), "Runtime scenario did not pass")
    require(report.get("world_partition") is True, "No live World Partition world")
    require(report.get("rhi") == "Vulkan" and report.get("fixed_timestep") is False,
            "Requires real Vulkan with variable simulation timestep")
    require("BiellaOpenWorldMap" in report.get("map", ""), "Wrong runtime map")
    for name, minimum in (("visible_cell_loads", 4), ("visible_cell_unloads", 4),
                          ("distinct_visible_cells", 4), ("navigation_checks", 20),
                          ("restores", 2), ("snapshots", 1), ("relocation_failures", 1)):
        require(report.get(name, 0) >= minimum, f"Missing {name} evidence")
    require(report.get("duplicates") == 0, "Duplicate persistent identity observed")
    require(report.get("input_route_distance_cm", 0) > 55000, "Insufficient input-driven route distance")

    with (directory / "frames.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == FIELDS, "Frame fields do not match runtime schema")
        rows = []
        for raw in reader:
            require(None not in raw and None not in raw.values(), "Malformed frame row")
            row = {key: float(value) for key, value in raw.items()}
            require(all(math.isfinite(value) for value in row.values()), "Nonfinite frame data")
            require(row["wall_delta_ms"] > 0 and row["sim_delta_ms"] >= 0, "Invalid clocks")
            require(row["loaded_cells"] >= row["visible_cells"] >= 0, "Invalid residency counts")
            require(row["used_physical_bytes"] > 0, "Missing real process memory sample")
            if rows:
                previous = rows[-1]
                require(row["frame"] == previous["frame"] + 1, "Missing rendered engine frame sample")
                delta = (row["wall_seconds"] - previous["wall_seconds"]) * 1000
                require(abs(delta - row["wall_delta_ms"]) < .01, "Wall clock interval mismatch")
                require(row["phase"] >= previous["phase"], "Scenario phase regressed")
            rows.append(row)
    require(len(rows) >= 100 and report["frames"] == len(rows) - 1, "Incomplete frame capture")
    intervals = sorted(row["wall_delta_ms"] for row in rows[1:])
    for name, fraction in (("p50", .5), ("p95", .95), ("p99", .99)):
        measured = intervals[math.floor((len(intervals) - 1) * fraction)]
        require(abs(report[f"frame_wall_ms_{name}"] - measured) < .001, f"Incorrect {name} wall statistic")
    require(abs(report["frame_wall_ms_max"] - intervals[-1]) < .001, "Incorrect max frame wall statistic")
    require(report["peak_process_resident_bytes"] == max(row["used_physical_bytes"] for row in rows),
            "Peak memory does not match measured process samples")

    # Phase IDs are part of this evidence schema. Explicit debug/mission
    # relocations never substitute for any input traversal checks below.
    traversal = [row for row in rows if row["phase"] in (1, 3, 6, 8)]
    require(traversal and max(row["x"] for row in traversal) > 18900,
            "Input traversal never reached distant region")
    for phase in (3, 8):
        require(any(row["phase"] == phase and row["x"] < 600 for row in rows),
                "Input return route did not revisit origin")
    require(any(abs(row["x"] - 8000) < 100 and row["y"] > 2200 and row["z"] < 130
                for row in traversal), "No indoor ground-level traversal")
    require(any(abs(row["x"] - 10000) < 100 and row["y"] > 3250 and row["z"] > 470
                for row in traversal), "No input-driven elevated terrace traversal")
    require(all(row["z"] >= 70 for row in traversal), "Input route exposed an unsupported floor/void")
    require(all(row["health"] == 93 for row in traversal), "Player health changed during streaming")
    require(all(row["ammo"] == (59 if row["phase"] in (1, 3) else 58) for row in traversal),
            "Ammo changed or reset during cell streaming")
    require(all(row["pressure"] == (20 if row["phase"] == 1 else 30) for row in traversal),
            "Authoritative pressure snapshot changed during cell streaming")

    events = (directory / "events.log").read_text()
    for name in ("fixture_world_reload_requested", "initial_shaders_ready", "dormancy_active_tick_restore",
                 "first_unload", "injury_restore", "defeat_unload", "defeat_restore",
                 "persistent_encounter_dormant", "persistent_encounter_awake",
                 "persistent_encounter_dormant_after_defeat", "persistent_encounter_awake_after_defeat",
                 "debug_relocation_recovered", "unavailable_relocation", "relocation_retry", "complete"):
        require(f"event={name} " in events, f"Missing observed {name}")
    require("event=failed " not in events and "continuity_failed" not in events, "Failure event present")
    files = [identity(directory / name) for name in ("streaming.json", "frames.csv", "events.log")]
    for name in CAPTURES:
        path = directory / "captures" / f"{name}.png"
        with Image.open(path) as capture:
            capture.load()
            require(capture.format == "PNG" and capture.width >= 320 and capture.height >= 180,
                    f"Invalid runtime capture {name}")
            require(max(ImageStat.Stat(capture.convert("RGB")).stddev) > 5,
                    f"Blank runtime capture {name}")
        files.append(identity(path))
    return {"task_id": "D02-01", "result": "PASS", "frames": len(rows),
            "wall_seconds": report["wall_seconds"], "visible_cell_loads": report["visible_cell_loads"],
            "visible_cell_unloads": report["visible_cell_unloads"],
            "frame_wall_ms_p95": report["frame_wall_ms_p95"],
            "frame_wall_ms_p99": report["frame_wall_ms_p99"],
            "peak_process_resident_bytes": report["peak_process_resident_bytes"],
            "capture_status": "GENERATED_DRAFT", "files": files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory), indent=2))


if __name__ == "__main__":
    main()
