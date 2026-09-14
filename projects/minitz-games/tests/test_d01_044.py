"""D01-44 adversarial verifier tests; fixtures are never runtime evidence."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from verify_d01_044 import frame_statistics, verify_log, verify_run


class NativePerformanceGates(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.settings = {"rhi": "Vulkan", "viewport_width": 32, "viewport_height": 24,
                         "fixed_timestep": False, "benchmarking": False,
                         "smooth_framerate": False, "use_fixed_framerate": False,
                         "cvars": {"r.VSync": "0", "t.MaxFPS": "0", "r.ScreenPercentage": "100",
                                   "r.DynamicRes.OperationMode": "0", "r.NGX.DLSS.Enable": "unavailable",
                                   "r.Streamline.DLSSG.Enable": "unavailable", "r.FidelityFX.FI.Enabled": "unavailable", "sg.EffectsQuality": "3"}}
        self.frames = []
        for i in range(16):
            stage = "warmup" if i < 2 else "measure" if i < 14 else "capture"
            phase = "terminal" if i == 6 else "travel" if i == 7 else "active"
            self.frames.append({"frame": 1001 + i, "wall_seconds": (i + 1) * .25,
                "wall_delta_ms": 250, "sim_delta_ms": 250, "stage": stage, "phase": phase,
                "cycle": 1 if i < 8 else 2, "game_ms": 15, "render_ms": 9, "rhi_ms": 1,
                "gpu_ms": 10, "game_wait_ms": 1, "render_wait_ms": 2, "swap_ms": 3,
                "pawn_count": 0 if phase == "travel" else 4,
                "autonomous_pawns": 3 if phase == "active" else 0,
                "player_x": i * 2, "player_y": 0, "player_z": 90, "view_yaw": i,
                "health": 80 if i < 8 else 100, "ammo": 59 if i < 8 else 60,
                "pressure": 2, "active_audio": 1, "active_vfx": 1})
        self.perf = {"schema": "biella.demo01.native_performance/v1", "result": "PASS",
            "requested_seconds": 3, "warmup_seconds": .5, "measured_seconds": 3,
            "frame_rows": 16, "measured_rows": 12, "cycles": 2, "restarts": 1,
            "terminal_frames": 1, "movement_distance": 30, "ai_movement_distance": 50,
            "shots_consumed": 1, "damage_observed": 20,
            "measure_start_wall_seconds": .5, "measure_end_wall_seconds": 3.5, "utc_start": "2026-09-05T12:00:00Z",
            "process_id": 1234, "platform_seconds_start": 100,
            "settings_begin": copy.deepcopy(self.settings), "settings": self.settings,
            "capture_files": ["warmup.png", "final.png"], "notes": []}
        self.events = []
        for name, wall, fields in [
            ("telemetry_ready", 10, {"format": "jsonl_utf8"}),
            ("perf_begin", 10, {"target_seconds": "3", "warmup_seconds": "0.5", "perf_wall_seconds": "0"}),
            ("perf_cycle_begin", 10.1, {"cycle": "1", "perf_wall_seconds": "0.1"}),
            ("perf_measure_begin", 10.5, {"perf_wall_seconds": "0.5"}),
            ("damage", 11, {"amount": "20", "health": "80", "source": "rival", "target": "player"}),
            ("weapon_fire", 11.1, {"damage": "10", "ammo": "59", "owner": "player", "target": "infected"}),
            ("perf_heartbeat", 11.2, {"frame": "1005"}),
            ("restart_requested", 12, {"previous_phase": "Active", "restart_count": "1"}),
            ("perf_restart", 12, {"perf_wall_seconds": "2"}),
            ("perf_cycle_begin", 12.1, {"cycle": "2", "perf_wall_seconds": "2.1"}),
            ("perf_heartbeat", 12.2, {"frame": "1009"}),
            ("perf_complete", 13.5, {"elapsed_wall_seconds": "3", "perf_wall_seconds": "3.5"}),
            ("telemetry_shutdown", 14, {})]:
            self.events.append({"schema": "biella.demo01.telemetry/v1", "session": "gate-fixture",
                "seq": len(self.events) + 1, "restart_count": int(wall >= 12),
                "event": name, "map": "BiellaGameplayMap", "wall_seconds": wall,
                "sim_seconds": wall, "fields": fields})
        (self.path / "runtime.stdout.log").write_text(
            "Result={Success} Name={NativePerformance}\n**** TEST COMPLETE. EXIT CODE: 0 ****\nD01_044_TEST COMPLETE")
        for name in self.perf["capture_files"]:
            image = Image.new("RGB", (32, 24), "black")
            image.putpixel((2, 2), (255, 64, 8))
            image.save(self.path / name)

    def verify(self):
        (self.path / "perf.json").write_text(json.dumps(self.perf))
        (self.path / "telemetry.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.events))
        with (self.path / "frames.csv").open("w") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.frames[0]))
            writer.writeheader()
            writer.writerows(self.frames)
        return verify_run(self.path, 3, 32, 24, .5)

    def test_gate_fixture_exercises_complete_parser(self):
        result = self.verify()
        self.assertEqual(result["frame_time"]["all_measurement"]["count"], 12)
        self.assertEqual(result["frame_time"]["terminal"]["count"], 1)
        self.assertEqual(result["frame_time"]["travel"]["count"], 1)
        self.assertEqual(result["frame_time"]["all_measurement"]["observed_fps"], 4)
        self.assertEqual(result["result"], "PASS")
        self.assertNotIn("fps_budget", result)
        self.assertEqual(result["frame_time"]["transition_intervals"]["count"], 2)
        transition = next(h for h in result["top_hitches"] if h["frame"] == 1009)
        self.assertEqual(transition["previous_phase"], "travel")
        self.assertEqual(transition["previous_cycle"], 1)
        self.assertEqual(transition["seconds_since_preceding_restart"], .25)

    def test_missing_frame_fails_even_with_repaired_row_count(self):
        del self.frames[4]
        self.perf["frame_rows"] -= 1
        self.perf["measured_rows"] -= 1
        with self.assertRaisesRegex(AssertionError, "frame sequence"):
            self.verify()

    def test_forged_clock_delta_rejected(self):
        self.frames[5]["wall_delta_ms"] = 16.666
        with self.assertRaisesRegex(AssertionError, "wall delta"):
            self.verify()

    def test_first_frame_clock_baseline_rejected(self):
        self.frames[0]["wall_delta_ms"] = 16.666
        with self.assertRaisesRegex(AssertionError, "wall delta"):
            self.verify()

    def test_nonfinite_frame_fields_rejected(self):
        for field in ("wall_delta_ms", "sim_delta_ms", "game_ms", "gpu_ms", "player_x"):
            original = self.frames[4][field]
            with self.subTest(field=field):
                self.frames[4][field] = "NaN"
                with self.assertRaisesRegex(AssertionError, "finite"):
                    self.verify()
            self.frames[4][field] = original

    def test_fixed_timestep_rejected(self):
        self.settings["fixed_timestep"] = True
        with self.assertRaisesRegex(AssertionError, "fixed_timestep"):
            self.verify()

    def test_native_settings_cannot_be_hidden_in_begin_snapshot(self):
        self.perf["settings_begin"]["fixed_timestep"] = True
        with self.assertRaisesRegex(AssertionError, "fixed_timestep"):
            self.verify()

    def test_frame_cap_and_upscaling_rejected(self):
        for key, value in (("t.MaxFPS", "60"), ("r.VSync", "1"),
                           ("r.ScreenPercentage", "66.67"), ("r.DynamicRes.OperationMode", "1")):
            original = self.settings["cvars"][key]
            with self.subTest(key=key):
                self.settings["cvars"][key] = value
                with self.assertRaisesRegex(AssertionError, key):
                    self.verify()
            self.settings["cvars"][key] = original

    def test_changed_quality_cvar_during_measurement_rejected(self):
        self.settings["cvars"]["sg.EffectsQuality"] = "2"
        with self.assertRaisesRegex(AssertionError, "settings changed"):
            self.verify()

    def test_missing_gpu_game_or_render_timing_fails_measurement(self):
        for key in ("gpu_ms", "game_ms", "render_ms"):
            originals = [frame[key] for frame in self.frames]
            for frame in self.frames:
                frame[key] = 0
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, key):
                self.verify()
            for frame, value in zip(self.frames, originals):
                frame[key] = value

    def test_wrong_resolution_rejected(self):
        self.settings["viewport_width"] = 64
        with self.assertRaisesRegex(AssertionError, "viewport"):
            self.verify()

    def test_wrong_render_path_rejected(self):
        self.settings["rhi"] = "Null"
        with self.assertRaisesRegex(AssertionError, "Vulkan"):
            self.verify()

    def test_duration_cannot_use_simulation_time(self):
        self.perf["measured_seconds"] = 5
        with self.assertRaisesRegex(AssertionError, "measured duration"):
            self.verify()

    def test_transition_samples_cannot_be_relabelled_warmup(self):
        self.frames[7]["stage"] = "warmup"
        with self.assertRaisesRegex(AssertionError, "stage order"):
            self.verify()

    def test_no_real_gameplay_cannot_pass(self):
        for frame in self.frames:
            frame["phase"] = "terminal"
            frame["pawn_count"] = 4
        with self.assertRaisesRegex(AssertionError, "active gameplay"):
            self.verify()

    def test_frozen_ai_rejected(self):
        for frame in self.frames:
            frame["autonomous_pawns"] = 0
        with self.assertRaisesRegex(AssertionError, "autonomous"):
            self.verify()

    def test_motionless_player_rejected(self):
        for frame in self.frames:
            frame["player_x"] = 0
        with self.assertRaisesRegex(AssertionError, "player movement"):
            self.verify()

    def test_missing_natural_damage_rejected(self):
        event = next(e for e in self.events if e["event"] == "damage")
        event["fields"]["amount"] = "0"
        with self.assertRaisesRegex(AssertionError, "damage"):
            self.verify()

    def test_synthetic_shot_counter_without_real_shot_rejected(self):
        next(e for e in self.events if e["event"] == "weapon_fire")["event"] = "unrelated"
        with self.assertRaisesRegex(AssertionError, "weapon_fire"):
            self.verify()

    def test_missing_restart_or_shutdown_rejected(self):
        for name in ("restart_requested", "telemetry_shutdown"):
            event = next(e for e in self.events if e["event"] == name)
            event["event"] = "unrelated"
            with self.subTest(name=name), self.assertRaises(AssertionError):
                self.verify()
            event["event"] = name

    def test_blank_or_wrong_size_capture_rejected(self):
        Image.new("RGB", (32, 24), "black").save(self.path / "warmup.png")
        with self.assertRaisesRegex(AssertionError, "blank"):
            self.verify()

    def test_png_header_without_decodable_data_rejected(self):
        path = self.path / "warmup.png"
        path.write_bytes(path.read_bytes()[:33])
        with self.assertRaises((AssertionError, OSError)):
            self.verify()

    def test_capture_cannot_escape_run_directory(self):
        self.perf["capture_files"][0] = "../outside.png"
        with self.assertRaisesRegex(AssertionError, "capture path"):
            self.verify()


class LogGates(unittest.TestCase):
    GOOD = "Result={Success} Name={NativePerformance}\n**** TEST COMPLETE. EXIT CODE: 0 ****\nD01_044_TEST COMPLETE"

    def test_runtime_fault_cannot_hide_behind_success(self):
        for fault in ("Fatal error:", "Ensure condition failed:", "Assertion failed:",
                      "LogTemp: Error: write failed", "VK_ERROR_DEVICE_LOST", "Result={Fail}"):
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                verify_log(self.GOOD + "\n" + fault, "")

    def test_missing_automation_and_new_warnings_rejected(self):
        for content in ("D01_044_TEST COMPLETE", self.GOOD + "\nLogTemp: Warning: new"):
            with self.subTest(content=content), self.assertRaises(AssertionError):
                verify_log(content, "")

    def test_baseline_warning_is_disclosed(self):
        old = "LogTemp: Warning: retained"
        self.assertEqual(verify_log(self.GOOD + "\n" + old, old)["warnings"], {old: 1})


class FrameStatistics(unittest.TestCase):
    def test_wall_fps_uses_total_elapsed_not_average_instantaneous_fps(self):
        result = frame_statistics([10, 20, 30, 40])
        self.assertEqual(result["observed_fps"], 40)
        self.assertEqual(result["p50_ms"], 25)
        self.assertEqual(result["p95_ms"], 38.5)
        self.assertEqual(result["hitches_gt_ms"]["33.3"], 1)

    def test_empty_phase_is_disclosed(self):
        self.assertEqual(frame_statistics([]), {"count": 0, "availability": "NO_SAMPLES"})


if __name__ == "__main__":
    unittest.main()
