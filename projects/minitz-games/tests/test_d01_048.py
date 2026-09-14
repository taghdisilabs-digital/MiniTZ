#!/usr/bin/env python3
"""Adversarial acceptance-validator fixtures; these are never gameplay evidence."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from PIL import Image

import verify_d01_048 as qualification


class AcceptanceVerifierTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "runtime.log"
        self.content = "\n".join([
            "LogPakFile: Display: Mounted Pak file '../../../BiellaGames/Content/Paks/BiellaGames-Linux.pak', mount point: '../../../'",
            "D01_SIGNAL GAME_INSTANCE_READY", "D01_SIGNAL WORLD_READY",
            "D01_SIGNAL HUD_READY", "D01_SIGNAL CONTROLLER_READY",
            "D01_039_TEST COMPLETE seed=1337 checkpoints=7 source=live_runtime",
            "Test Completed. Result={Success} Name={DeterministicPlaytest} Path={BiellaGames.Demo01.DeterministicPlaytest}",
            "**** TEST COMPLETE. EXIT CODE: 0 ****", "LogExit: Exiting.",
        ])
        self.run = {"name": "core-nullrhi", "suite": "DeterministicPlaytest", "renderer": "nullrhi",
                    "runtime": {"returncode": 0, "timed_out": False}}
        self.save_log(self.content)

    def identity(self, path):
        data = path.read_bytes()
        return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

    def save_log(self, text):
        self.path.write_text(text)
        self.run["runtime"]["log"] = self.identity(self.path)

    def test_hash_and_size_verified_against_disk(self):
        self.assertEqual(qualification.verify_identity(self.identity(self.path)), self.path)

    def test_tampered_same_length_file_rejected(self):
        original = self.identity(self.path)
        self.path.write_text(self.content.replace("seed=1337", "seed=1338"))
        with self.assertRaisesRegex(AssertionError, "hash"):
            qualification.verify_identity(original)

    def test_tampered_size_rejected(self):
        original = self.identity(self.path)
        original["bytes"] += 1
        with self.assertRaisesRegex(AssertionError, "size"):
            qualification.verify_identity(original)

    def test_missing_artifact_rejected(self):
        original = self.identity(self.path)
        self.path.unlink()
        with self.assertRaises(AssertionError):
            qualification.verify_identity(original)

    def test_live_log_requires_all_launch_completion_signals(self):
        self.assertIn("D01_039_TEST COMPLETE", qualification.verify_runtime(self.run))

    def test_nonzero_exit_rejected_despite_success_log(self):
        self.run["runtime"]["returncode"] = 1
        with self.assertRaisesRegex(AssertionError, "exit"):
            qualification.verify_runtime(self.run)

    def test_timeout_rejected_despite_success_log(self):
        self.run["runtime"]["timed_out"] = True
        with self.assertRaisesRegex(AssertionError, "timeout"):
            qualification.verify_runtime(self.run)

    def test_each_missing_required_log_signal_rejected(self):
        for fragment in ("Mounted Pak file", "GAME_INSTANCE_READY", "WORLD_READY", "HUD_READY",
                         "CONTROLLER_READY", "Result={Success}", "TEST COMPLETE. EXIT CODE: 0", "LogExit: Exiting."):
            with self.subTest(fragment=fragment):
                self.save_log(self.content.replace(fragment, "absent"))
                with self.assertRaises(AssertionError):
                    qualification.verify_runtime(self.run)

    def test_wrong_suite_success_does_not_qualify_run(self):
        self.save_log(self.content.replace("Name={DeterministicPlaytest}", "Name={Unrelated}"))
        with self.assertRaises(AssertionError):
            qualification.verify_runtime(self.run)

    def test_success_before_gameplay_completion_rejected(self):
        lines = self.content.splitlines()
        lines[5], lines[6] = lines[6], lines[5]
        self.save_log("\n".join(lines))
        with self.assertRaisesRegex(AssertionError, "order"):
            qualification.verify_runtime(self.run)

    def test_observed_runtime_failures_rejected(self):
        for fault in ("LogTemp: Error: content load failed", "Fatal error: failed", "Assertion failed: x",
                      "Ensure condition failed: x", "Result={Fail}", "Segmentation fault", "D01_039_TEST FAIL broken"):
            with self.subTest(fault=fault):
                self.save_log(self.content + "\n" + fault)
                with self.assertRaisesRegex(AssertionError, "error|failure"):
                    qualification.verify_runtime(self.run)

    def test_existing_warning_retained_without_false_failure(self):
        self.save_log(self.content + "\nLogVulkanRHI: Warning: Found 1 unfreed allocations!")
        self.assertIn("unfreed", qualification.verify_runtime(self.run))

    def test_vulkan_requires_observed_renderer(self):
        self.run.update(name="core-vulkan", renderer="vulkan")
        with self.assertRaisesRegex(AssertionError, "Vulkan"):
            qualification.verify_runtime(self.run)
        self.save_log(self.content + "\nLogVulkanRHI: Display: Vulkan swapchain created")
        qualification.verify_runtime(self.run)

    def test_complete_coverage_is_seven_independent_suites(self):
        runs = [{"name": name, "suite": values[0], "renderer": values[1], "extraction": str(self.root / name)}
                for name, values in qualification.EXPECTED_RUNS.items()]
        self.assertEqual(len(qualification.verify_coverage(runs)), 7)
        self.runs = runs

    def test_missing_duplicate_wrong_suite_or_reused_extraction_rejected(self):
        self.test_complete_coverage_is_seven_independent_suites()
        mutations = [self.runs[:-1], self.runs + [self.runs[0]]]
        for field, value in (("suite", "Unrelated"), ("renderer", "nullrhi"),
                             ("extraction", self.runs[0]["extraction"])):
            mutated = copy.deepcopy(self.runs)
            mutated[-1][field] = value
            mutations.append(mutated)
        for runs in mutations:
            with self.subTest(runs=runs):
                with self.assertRaises(AssertionError):
                    qualification.verify_coverage(runs)

    def test_decoded_frame_is_required(self):
        capture = self.root / "frame.png"
        capture.write_bytes(b"not a PNG")
        with self.assertRaises((AssertionError, OSError)):
            qualification.verify_frame(self.identity(capture))

    def test_blank_and_wrong_resolution_frames_rejected(self):
        capture = self.root / "frame.png"
        for size in ((1280, 720), (640, 360)):
            Image.new("RGB", size, "black").save(capture)
            with self.subTest(size=size), self.assertRaises(AssertionError):
                qualification.verify_frame(self.identity(capture))

    def test_varied_full_size_frame_decodes(self):
        capture = self.root / "frame.png"
        frame = Image.new("RGB", (1280, 720), "black")
        frame.paste("white", (0, 0, 640, 720))
        frame.save(capture)
        self.assertEqual(qualification.verify_frame(self.identity(capture))["size"], [1280, 720])

    def test_mutated_and_empty_source_snapshots_rejected(self):
        before = [self.identity(self.path)]
        qualification.verify_snapshot(before, copy.deepcopy(before), "source")
        for after in ([], [{**before[0], "sha256": "0" * 64}]):
            with self.subTest(after=after), self.assertRaises(AssertionError):
                qualification.verify_snapshot(before, after, "source")
        with self.assertRaises(AssertionError):
            qualification.verify_snapshot([], [], "source")

    def test_duplicate_snapshot_cannot_count_as_multiple_files(self):
        repeated = [self.identity(self.path)] * 2
        with self.assertRaisesRegex(AssertionError, "Duplicate"):
            qualification.verify_snapshot(repeated, copy.deepcopy(repeated), "source")

    def test_report_does_not_trust_self_reported_pass(self):
        with self.assertRaises(AssertionError):
            qualification.verify({"task_id": "D01-48", "result": "PASS", "runs": []})

    def test_tooling_replay_rejects_missing_duplicate_or_changed_validator(self):
        tools = []
        for name in ('verify_d01_048.py', 'verify_d01_039.py', 'verify_d01_031.py',
                     'verify_d01_033.py', 'run_d01_042.py', 'run_d01_039.py'):
            path = self.root / name
            path.write_text('fixture')
            tools.append(self.identity(path))
        report = {'runner': self.identity(self.path), 'verification_tools': tools}
        qualification.verify_tooling(report)
        for incomplete in ([], tools[:-1], [tools[0]] * len(tools)):
            with self.subTest(incomplete=incomplete), self.assertRaises(AssertionError):
                qualification.verify_tooling({**report, 'verification_tools': incomplete})
        Path(tools[0]['path']).write_text('changed')
        with self.assertRaisesRegex(AssertionError, 'hash'):
            qualification.verify_tooling(report)


if __name__ == "__main__":
    unittest.main()
