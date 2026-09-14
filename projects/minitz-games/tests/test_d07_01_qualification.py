"""D07 diagnostic/measurement controls. Synthetic faults are NOT gameplay evidence."""
import copy
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import run_d07_01_qualification as q


GOOD_LOG = "Result={Success} Name={NativePerformance}\n**** TEST COMPLETE. EXIT CODE: 0 ****\nD01_044_TEST COMPLETE\n"


class QualificationControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="d07-controls-")
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)

    def test_exact_current_warnings_accepted_not_silenced(self):
        log = GOOD_LOG + "\n".join(q.NEW_WARNINGS)
        report = q.native_log(log, "")
        self.assertEqual(set(report["warnings"]), set(q.NEW_WARNINGS))

    def test_unknown_warning_rejected(self):
        with self.assertRaisesRegex(AssertionError, "Unclassified"):
            q.native_log(GOOD_LOG + "LogNew: Warning: unexpected pipeline failure", "")

    def test_missing_completion_rejected(self):
        with self.assertRaisesRegex(AssertionError, "completion marker"):
            q.native_log("", "")

    def test_runtime_diagnostics_reject_fatal_assert_ensure_device_and_telemetry(self):
        faults = ("Fatal error: control", "Assertion failed: control", "Ensure condition failed: control",
                  "LogTemp: Error: control", "VK_ERROR_DEVICE_LOST", "D01_TELEMETRY_ERROR",
                  "Result={Fail} Name={NativePerformance}")
        for fault in faults:
            with self.subTest(fault=fault):
                (self.out / "runtime.stdout.log").write_text(GOOD_LOG + fault)
                with self.assertRaises(AssertionError):
                    q.diagnostics(self.out, "native720")

    def test_dataflow_diagnostic_allowed_only_exactly_before_world_boundary(self):
        text = ("LogClass: Error: StructProperty FDataflowToolNodeSnapshot::Date is not initialized properly "
                "even though its struct probably has a custom default constructor. "
                "Non deterministic fields should use UPROPERTY(Meta = (IgnoreForMemberInitializationTest)) "
                "to avoid errors from this test. Module:DataflowNodes File:Public/Dataflow/DataflowToolNode.h\n")
        self.assertFalse(q.runtime_has_task_error(text + "D02_STREAM WORLD_READY\n"))
        self.assertTrue(q.runtime_has_task_error("D02_STREAM WORLD_READY\n" + text))
        self.assertTrue(q.runtime_has_task_error(text.replace("Date", "OtherField") + "D02_STREAM WORLD_READY\n"))

    def test_raw_and_validation_receipt_mutations_rejected(self):
        (self.out / "trace.txt").write_text("original raw trace")
        report = {"result": "PASS", "spec": q.SPECS["native720"], "runtime_input_digest": "inputs",
                  "raw": q.raw_identities(self.out), "runtime": {"returncode": 0, "watchdog_failure": None,
                  "log_finalization": {"closed": True}, "survivors": [], "unreal_process_identities": [{"pid": 42}]}}
        path = self.out / "validation.json"
        q.write_json(path, report)
        pointer = {"result": "PASS", "runtime_input_digest": "inputs", "directory": str(self.out),
                   "validation": str(path), "validation_identity": q.file_identity(path)}
        self.assertEqual(q.retained_report("native720", pointer, "inputs")["result"], "PASS")
        with self.assertRaisesRegex(AssertionError, "runtime inputs changed"):
            q.retained_report("native720", pointer, "changed-inputs")
        (self.out / "trace.txt").write_text("mutated raw trace")
        with self.assertRaisesRegex(AssertionError, "raw evidence bytes changed"):
            q.retained_report("native720", pointer, "inputs")
        path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(AssertionError, "receipt identity changed"):
            q.retained_report("native720", pointer, "inputs")

    def test_all_observed_intervals_and_recurring_hitches_retained(self):
        rows = [dict(frame=i, wall_delta_ms=v, sim_delta_ms=10, phase="active", cycle=i % 2)
                for i, v in enumerate((10, 10, 100, 10, 100), 1)]
        with (self.out / "frames.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        report = q.frame_observations(self.out, "streaming")
        self.assertEqual(report["frame_time"]["count"], 5)
        self.assertEqual(report["adjacent_frame_time"]["count"], 4)
        self.assertEqual(report["recurring_hitches_over_50ms"]["count"], 2)
        self.assertAlmostEqual(report["simulation_seconds_per_wall_second"], 50/230)
        text = (self.out / "frames.csv").read_text()
        (self.out / "frames.csv").write_text(text.replace("100", "nan", 1))
        with self.assertRaisesRegex(AssertionError, "Nonfinite"):
            q.frame_observations(self.out, "streaming")

    def test_runtime_identity_excludes_volatile_controller_state(self):
        inputs = q.runtime_inputs()
        self.assertGreater(len(inputs), 100)
        self.assertFalse(any("03_BIELLA_CURRENT_STATE" in row["path"] or "04_BIELLA_ACTIVE_TASK" in row["path"] for row in inputs))

    def test_audio_uses_accepted_wall_clock_mixer_and_gameplay_map(self):
        command = q.command("audio", self.out)
        self.assertIn("/Game/Maps/BiellaGameplayMap", command)
        self.assertNotIn("-DeterministicAudio", command)
        self.assertIn("-UseFixedTimeStep", command)

    def test_clean_warm_is_private_and_does_not_delete_shared_cache(self):
        command = q.command("shadercold", self.out, self.out / "private-cache")
        self.assertEqual(command[0], "bwrap")
        self.assertIn("--bind", command)
        self.assertIn("--dev-bind", command)
        self.assertTrue(any("__GL_SHADER_DISK_CACHE_PATH=" in token for token in command))
        self.assertFalse(any("ClearPSODriverCache" in token for token in command))

    def test_support_proof_requires_exact_receipt_and_raw_bytes(self):
        from report_d07_01_qualification import verify_support
        raw = self.out / "control.txt"
        raw.write_text("observed control")
        image = self.out / "reviewed.png"
        image.write_bytes(b"synthetic identity-only control, not PNG proof")
        receipt = self.out / "validation.json"
        q.write_json(receipt, {"result": "PASS", "tests_run": 50, "failures": 0, "errors": 0,
                              "source": [], "raw": [q.file_identity(raw)]})
        report = {"diagnostic_controls": {"report": {"result": "PASS", "watchdog_expected_rejection": True,
                  "receipt": q.file_identity(receipt)}},
                  "visual_observations": {"report": {"observations": [{"image": q.file_identity(image)}]}}}
        verify_support(report)
        raw.write_text("changed")
        with self.assertRaisesRegex(AssertionError, "raw bytes changed"):
            verify_support(report)
        receipt.write_text("changed")
        with self.assertRaisesRegex(AssertionError, "receipt changed"):
            verify_support(report)


def main():
    root = q.ROOT / "diagnostics"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = root / stamp
    out.mkdir()
    output = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(QualificationControls)
    for name in ("test_d01_044", "test_d01_044_resources"):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    (out / "unittest.txt").write_text(output.getvalue())
    # Benign real process fault injection: a sleeping child exceeds a short
    # task-owned deadline. No game/source/driver failure is manufactured.
    watchdog_dir = out / "watchdog-control"
    watchdog_dir.mkdir()
    watchdog_command = [sys.executable, "-c", "import time; print('EXPECTED HANG CONTROL', flush=True); time.sleep(30)"]
    watchdog = q.monitor(watchdog_command, watchdog_dir, .5)
    watchdog_ok = watchdog["watchdog_failure"] == "overall process deadline" and watchdog["returncode"] != 0 and not watchdog["survivors"] and watchdog["log_finalization"]["closed"]
    (out / "positive.log").write_text(GOOD_LOG)
    for key, fault in {"fatal": "Fatal error: synthetic control", "assert": "Assertion failed: synthetic control", "device": "VK_ERROR_DEVICE_LOST", "telemetry": "D01_TELEMETRY_ERROR"}.items():
        (out / (key + ".log")).write_text(GOOD_LOG + fault + "\n")
    report = {"task_id": "D07-01", "result": "PASS" if result.wasSuccessful() and watchdog_ok else "FAIL",
              "scope": "Synthetic diagnostic/measurement controls only; never gameplay, crash-free or target-tier evidence.",
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "watchdog_command": watchdog_command, "watchdog": watchdog,
              "source": [q.file_identity(Path(__file__)), q.file_identity(Path(q.__file__))],
              "raw": q.raw_identities(out)}
    q.write_json(out / "validation.json", report)
    q.write_json(root / "validation.json", {"result": report["result"], "tests_run": result.testsRun,
        "receipt": q.file_identity(out / "validation.json"), "watchdog_expected_rejection": watchdog_ok})
    print(output.getvalue())
    print(json.dumps({"result": report["result"], "evidence": str(out / "validation.json")}))
    if report["result"] != "PASS":
        q.failure("qualification.diagnostic_controls", "Control suite failed; inspect retained traceback", out / "validation.json")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
