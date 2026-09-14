"""Mutate retained real D01-44 smoke evidence; never submit mutations as runtime proof."""
import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from run_d01_044 import verify_resources
from verify_d01_044 import verify_run


PROJECT = Path(__file__).resolve().parents[1]
CAPTURE = PROJECT / "Build/Demo01/D01-044-runs/20260905T094646.479673Z-1280x720"


class RetainedEvidence(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / CAPTURE.name
        self.path.mkdir()
        for name in ("frames.csv", "perf.json", "telemetry.jsonl", "runtime.stdout.log", "resources.jsonl"):
            shutil.copy2(CAPTURE / name, self.path / name)
        self.perf = json.loads((self.path / "perf.json").read_text())
        self.samples = [json.loads(line) for line in (self.path / "resources.jsonl").read_text().splitlines()]
        clock = str(self.perf["settings"]["platform_clock_id"])
        origin = self.perf["platform_seconds_start"]
        lower = origin + self.perf["measure_start_wall_seconds"]
        upper = origin + self.perf["measure_end_wall_seconds"]
        self.selected = [s for s in self.samples if lower <= s["clocks"][clock] <= upper]

    def resources(self):
        (self.path / "resources.jsonl").write_text("".join(json.dumps(s) + "\n" for s in self.samples))
        return verify_resources(self.path, self.perf)

    def test_original_native_smoke_and_resource_evidence_passes(self):
        result = verify_run(self.path, 30, 1280, 720, 5)
        self.assertEqual(result["result"], "PASS")
        measured = result["frame_time"]["all_measurement"]
        self.assertEqual(measured["count"], 2138)
        self.assertAlmostEqual(measured["duration_seconds"], 30.012386816, places=7)
        self.assertEqual(sum(result["frame_time"][p]["count"] for p in ("active", "terminal", "travel")), measured["count"])
        self.assertGreater(result["frame_time"]["transition_intervals"]["max_ms"], 50)
        hitches = [h for h in result["top_hitches"] if h["transition_interval"]]
        self.assertTrue(hitches)
        self.assertTrue(all(h["seconds_since_preceding_restart"] is not None for h in hitches))
        resource = self.resources()
        self.assertEqual(resource["pid"], self.perf["process_id"])
        self.assertGreater(resource["samples"], 20)

    def test_missing_measured_pid_rejected(self):
        self.selected[len(self.selected) // 2]["unreal"] = []
        with self.assertRaisesRegex(AssertionError, "exact Unreal PID"):
            self.resources()

    def test_same_pid_with_reused_process_identity_rejected(self):
        pid = self.perf["process_id"]
        next(p for p in self.selected[3]["unreal"] if p["pid"] == pid)["start_ticks"] += 1
        with self.assertRaisesRegex(AssertionError, "PID reused"):
            self.resources()

    def test_wrong_gpu_graphics_pid_rejected(self):
        gpu = self.selected[3]["gpus"][0]
        pid = self.perf["process_id"]
        next(p for p in gpu["processes"] if p["pid"] == pid)["pid"] = -1
        with self.assertRaisesRegex(AssertionError, "measured graphics PID"):
            self.resources()

    def test_compute_process_cannot_substitute_for_graphics_process(self):
        gpu = self.selected[3]["gpus"][0]
        next(p for p in gpu["processes"] if p["pid"] == self.perf["process_id"])["type"] = "C"
        with self.assertRaisesRegex(AssertionError, "graphics process"):
            self.resources()

    def test_gpu_identity_change_rejected(self):
        self.selected[3]["gpus"][0]["uuid"] = "another-gpu"
        with self.assertRaisesRegex(AssertionError, "GPU identity changed"):
            self.resources()

    def test_resource_clock_gap_cannot_be_hidden_by_enough_total_samples(self):
        middle = len(self.selected) // 2
        deleted_ids = {id(s) for s in self.selected[middle:middle + 4]}
        self.samples = [s for s in self.samples if id(s) not in deleted_ids]
        with self.assertRaisesRegex(AssertionError, "stalled"):
            self.resources()

    def test_outside_window_samples_cannot_replace_measurement_coverage(self):
        clock = str(self.perf["settings"]["platform_clock_id"])
        for sample in self.selected:
            sample["clocks"][clock] -= 1000
        with self.assertRaisesRegex(AssertionError, "Insufficient OS samples"):
            self.resources()

    def test_device_utilization_cannot_be_nan(self):
        self.selected[3]["gpus"][0]["utilization_percent"] = float("nan")
        with self.assertRaisesRegex(AssertionError, "invalid resource"):
            self.resources()

    def test_missing_per_process_vram_does_not_use_device_vram(self):
        gpu = self.selected[3]["gpus"][0]
        next(p for p in gpu["processes"] if p["pid"] == self.perf["process_id"])["used_memory"] = "N/A"
        with self.assertRaisesRegex(AssertionError, "Per-process VRAM"):
            self.resources()

    def test_real_frame_removal_cannot_pass_repaired_counts(self):
        with (self.path / "frames.csv").open() as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            frames = list(reader)
        index = next(i for i, frame in enumerate(frames) if frame["stage"] == "measure") + 10
        del frames[index]
        self.perf["frame_rows"] -= 1
        self.perf["measured_rows"] -= 1
        (self.path / "perf.json").write_text(json.dumps(self.perf))
        with (self.path / "frames.csv").open("w") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(frames)
        with self.assertRaisesRegex(AssertionError, "frame sequence"):
            verify_run(self.path, 30, 1280, 720, 5)

    def test_final_capture_damage_cannot_substitute_for_measured_gameplay(self):
        events = [json.loads(line) for line in (self.path / "telemetry.jsonl").read_text().splitlines()]
        begin = next(e for e in events if e["event"] == "perf_begin")
        origin = begin["wall_seconds"] - float(begin["fields"]["perf_wall_seconds"])
        lower = origin + self.perf["measure_start_wall_seconds"]
        upper = origin + self.perf["measure_end_wall_seconds"]
        for event in events:
            if lower <= event["wall_seconds"] <= upper and event["event"] == "damage":
                event["fields"]["amount"] = "0"
        (self.path / "telemetry.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
        with self.assertRaisesRegex(AssertionError, "No live positive damage"):
            verify_run(self.path, 30, 1280, 720, 5)


if __name__ == "__main__":
    unittest.main()
