"""False-success gate tests. Runtime mutation tests use retained real captures."""
import unittest
import json
from pathlib import Path
import tempfile
import subprocess
import sys

from verify_d01_043 import classify_log, qualification_mode, verify_capture
from run_d01_043 import finalize_log


class QualificationGates(unittest.TestCase):
    def test_short_run_cannot_claim_qualification(self):
        self.assertEqual(qualification_mode(10, 1), "SMOKE_ONLY")
        self.assertEqual(qualification_mode(899, 20), "SMOKE_ONLY")
        self.assertEqual(qualification_mode(900, 19), "SMOKE_ONLY")
        self.assertEqual(qualification_mode(900, 20), "QUALIFICATION")

    def test_crash_ensure_or_error_cannot_hide_behind_success(self):
        good = "Result={Success} Name={StabilitySoak}\n**** TEST COMPLETE. EXIT CODE: 0 ****\nD01_043_TEST COMPLETE"
        self.assertEqual(classify_log(good, "")["warnings"], {})
        for fault in ("Fatal error:", "Ensure condition failed:", "Assertion failed:",
                      "LogTemp: Error: write failed", "VK_ERROR_DEVICE_LOST", "Result={Fail}"):
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                classify_log(good + "\n" + fault, "")

    def test_missing_completion_fails(self):
        with self.assertRaises(AssertionError):
            classify_log("Result={Success} Name={StabilitySoak}", "")

    def test_new_warning_fails_even_if_old_warning_is_known(self):
        good = "Result={Success} Name={StabilitySoak}\n**** TEST COMPLETE. EXIT CODE: 0 ****\nD01_043_TEST COMPLETE"
        old = "LogNavigation: Warning: existing diagnostic"
        self.assertEqual(classify_log(good + "\n" + old, old)["warnings"], {old: 1})
        with self.assertRaises(AssertionError):
            classify_log(good + "\nLogTemp: Warning: new fault", old)


class LogFinalizationGates(unittest.TestCase):
    def test_waits_for_detached_late_writer_before_hashing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stdout.log"
            with path.open("wb") as log:
                parent = subprocess.Popen([sys.executable, "-c",
                    "import os,time; pid=os.fork(); "
                    "os._exit(0) if pid else None; time.sleep(.35); "
                    "print('late daemon trailer',flush=True); os._exit(0)"], stdout=log)
                parent.wait(timeout=5)
            result = finalize_log(path, 5)
            self.assertTrue(result["closed"])
            self.assertTrue(result["observed_writers"])
            self.assertEqual(path.read_text(), "late daemon trailer\n")

    def test_unclosed_writer_fails_finalization_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stdout.log"
            with path.open("wb") as log:
                child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"], stdout=log)
            try:
                result = finalize_log(path, .05)
                self.assertFalse(result["closed"])
                self.assertTrue(result["remaining_writers"])
            finally:
                child.terminate()
                child.wait(timeout=5)


class RetainedCaptureGates(unittest.TestCase):
    """Mutations of the real two-cycle smoke, never submitted as runtime evidence."""
    def setUp(self):
        project = Path(__file__).resolve().parents[1]
        self.reference = project / "Build/Demo01/D01-042-qualified-predecessor/20260905T084808.360613Z-nullrhi-02df4931/run-01.telemetry.jsonl"
        smoke = project / "Build/Demo01/D01-043-runs/20260905T090359.802435Z/soak.telemetry.jsonl"
        self.events = [json.loads(line) for line in smoke.read_text().splitlines()]
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "mutation.jsonl"

    def event(self, name):
        return next(e for e in self.events if e["event"] == name)

    def verify(self):
        self.path.write_text("".join(json.dumps(e) + "\n" for e in self.events))
        return verify_capture(self.path, 10, 2, self.reference)

    def test_original_smoke_passes_only_as_smoke(self):
        self.assertEqual(self.verify()["mode"], "SMOKE_ONLY")

    def test_changed_session_rejected(self):
        self.events[10]["session"] = "replacement-process"
        with self.assertRaisesRegex(AssertionError, "Session changed"):
            self.verify()

    def test_missing_sequence_rejected(self):
        del self.events[10]
        with self.assertRaisesRegex(AssertionError, "sequence"):
            self.verify()

    def test_truncated_shutdown_rejected(self):
        self.events.pop()
        with self.assertRaisesRegex(AssertionError, "lifecycle"):
            self.verify()

    def test_insufficient_elapsed_rejected(self):
        self.event("soak_complete")["fields"]["elapsed_wall_seconds"] = "9"
        with self.assertRaisesRegex(AssertionError, "duration"):
            self.verify()

    def test_feedback_overflow_rejected(self):
        self.event("soak_heartbeat")["fields"]["active_vfx"] = "25"
        with self.assertRaisesRegex(AssertionError, "cap exceeded"):
            self.verify()

    def test_missing_actor_rejected(self):
        self.event("soak_heartbeat")["fields"]["actor_count"] = "3"
        with self.assertRaisesRegex(AssertionError, "actor membership"):
            self.verify()

    def test_dirty_final_baseline_rejected(self):
        self.event("soak_complete")["fields"]["clean_active_baseline"] = "false"
        with self.assertRaisesRegex(AssertionError, "Clean baseline"):
            self.verify()

    def test_frozen_natural_encounter_rejected(self):
        self.event("soak_natural_end")["fields"]["autonomous_ticks_enabled"] = "false"
        with self.assertRaisesRegex(AssertionError, "AI was frozen"):
            self.verify()

    def test_motionless_natural_encounter_rejected(self):
        self.event("soak_natural_end")["fields"]["natural_max_displacement"] = "0"
        with self.assertRaisesRegex(AssertionError, "did not move"):
            self.verify()

    def test_stalled_frames_rejected(self):
        beats = [e for e in self.events if e["event"] == "soak_heartbeat"]
        beats[1]["fields"]["frame_counter"] = beats[0]["fields"]["frame_counter"]
        with self.assertRaisesRegex(AssertionError, "Frame progress"):
            self.verify()

    def test_corrupted_gameplay_result_rejected(self):
        self.event("weapon_fire")["fields"]["damage"] = "999"
        with self.assertRaisesRegex(AssertionError, "semantic trace"):
            self.verify()

    def test_no_autonomous_combat_rejected(self):
        a, b = self.event("soak_natural_begin")["seq"], self.event("soak_natural_end")["seq"]
        self.events = [e for e in self.events if not (a < e["seq"] < b and e["event"] in ("damage", "weapon_fire"))]
        for i, e in enumerate(self.events, 1):
            e["seq"] = i
        with self.assertRaisesRegex(AssertionError, "No live autonomous combat"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
