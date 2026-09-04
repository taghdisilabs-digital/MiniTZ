from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ops.control_gateway.biella_control_runner import ProjectRunner


class CaptureExec:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, cwd, env, timeout):
        self.calls.append((list(argv), Path(cwd), dict(env), timeout))
        if "exec" in argv:
            return 0, "banner\ncodex\nPROJECT_RESULT\ntokens used\n10\n"
        return 0, "STATUS_OK\n"


class ProjectRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.website = root / "website"
        self.engine = root / "engine"
        self.games = root / "games"
        for path in (self.website, self.engine, self.games):
            path.mkdir()
        self.capture = CaptureExec()
        self.events = []
        self.runner = ProjectRunner(
            lane_workdirs={"Website": self.website, "Engine": self.engine, "Games": self.games},
            runtime_env_loader=lambda: {"GROQ_API_KEY": "secret-not-printed"},
            exec_command=self.capture,
            background=lambda fn: fn(),
            qwen_catalog=Path("/usr/local/lib/biella-ai/qwen-codex-model-catalog.json"),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def publish(self, lane, event):
        self.events.append((lane, event))

    def test_dialog_uses_unrestricted_codex_bounded_by_task_contract(self):
        dialog_id = self.runner.start_dialog("Website", "inspect current source", self.publish)
        self.assertTrue(dialog_id.startswith("dialog-"))
        argv, cwd, env, timeout = self.capture.calls[0]
        self.assertEqual(cwd, self.website)
        self.assertEqual(argv[0], "/usr/local/bin/biella-local-agent")
        self.assertNotIn("workspace-write", argv)
        self.assertNotIn("-a", argv)
        self.assertIn("-C", argv)
        self.assertIn("exec", argv)
        self.assertEqual(env["GROQ_API_KEY"], "secret-not-printed")
        self.assertEqual(self.events[-1][1]["text"], "PROJECT_RESULT")

    def test_run_capability_uses_exact_allowlisted_commands(self):
        result = self.runner.run_capability("Engine", "workstation.status", True, self.publish)
        self.assertEqual(result["status"], "COMPLETE")
        argv, cwd, env, timeout = self.capture.calls[-1]
        self.assertEqual(argv, ["/usr/local/bin/biella", "status"])
        self.assertEqual(cwd, self.engine)
        result = self.runner.run_capability("Games", "git.status.current", False, self.publish)
        argv, cwd, env, timeout = self.capture.calls[-1]
        self.assertEqual(argv, ["git", "-C", str(self.games), "status", "--short", "--branch"])

    def test_unknown_capability_is_rejected(self):
        with self.assertRaises(ValueError):
            self.runner.run_capability("Engine", "shell.exec", False, self.publish)


    def test_dialog_prepends_installed_low_noise_work_contract(self):
        contract = Path(self.tmp.name) / "work-contract.md"
        contract.write_text("LOW_NOISE_CONTRACT\nExecution is unrestricted on the Biella workstation\nContinue the current highest-priority incomplete task\n")
        runner = ProjectRunner(
            lane_workdirs={"Website": self.website, "Engine": self.engine, "Games": self.games},
            runtime_env_loader=lambda: {},
            exec_command=self.capture,
            background=lambda fn: fn(),
            qwen_catalog=Path("/usr/local/lib/biella-ai/qwen-codex-model-catalog.json"),
            work_contract=contract,
        )
        runner.start_dialog("Engine", "continue", self.publish)
        prompt = self.capture.calls[-1][0][-1]
        self.assertIn("LOW_NOISE_CONTRACT", prompt)
        self.assertIn("Operator message:\ncontinue", prompt)


if __name__ == "__main__":
    unittest.main()
