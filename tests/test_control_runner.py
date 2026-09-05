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
        self.assertEqual(argv[0], "/usr/local/bin/biella-codex")
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


    def test_dialog_uses_progressive_shared_context_guidance(self):
        runner = ProjectRunner(
            lane_workdirs={"Website": self.website, "Engine": self.engine, "Games": self.games},
            runtime_env_loader=lambda: {},
            exec_command=self.capture,
            background=lambda fn: fn(),
        )
        runner.start_dialog("Engine", "continue", self.publish)
        prompt = self.capture.calls[-1][0][-1]
        self.assertIn("progressive context", prompt)
        self.assertIn("shared /root/.codex", prompt)
        self.assertIn("Operator message:\ncontinue", prompt)

    def test_games_dialog_queues_into_active_production_session(self):
        runtime = Path(self.tmp.name) / "runtime.json"
        runtime.write_text('{"status":"RUNNING","task_id":"D02-01","session_task_id":"D02-01","task_session_id":"session-d02"}')
        runner = ProjectRunner(
            lane_workdirs={"Website": self.website, "Engine": self.engine, "Games": self.games},
            runtime_env_loader=lambda: {},
            exec_command=self.capture,
            background=lambda fn: fn(),
            production_runtime_path=runtime,
            production_active=lambda: True,
        )
        runner.start_dialog("Games", "focus nav readiness", self.publish)
        argv = self.capture.calls[-1][0]
        self.assertIn("queue", argv)
        self.assertIn("--thread", argv)
        self.assertIn("session-d02", argv)
        self.assertNotIn("exec", argv)
        kinds = [event[1].get("type") for event in self.events]
        self.assertIn("dialog.operator", kinds)
        self.assertIn("dialog.queued", kinds)

    def test_standalone_dialog_is_single_flight_per_lane(self):
        pending = []
        runner = ProjectRunner(
            lane_workdirs={"Website": self.website, "Engine": self.engine, "Games": self.games},
            runtime_env_loader=lambda: {},
            exec_command=self.capture,
            background=lambda fn: pending.append(fn),
            production_active=lambda: False,
        )
        runner.start_dialog("Website", "first", self.publish)
        with self.assertRaisesRegex(Exception, "dialog already active"):
            runner.start_dialog("Website", "second", self.publish)
        pending[0]()
        runner.start_dialog("Website", "third", self.publish)


    def test_production_journal_tailer_replays_existing_events(self):
        journal = Path(self.tmp.name) / "events.jsonl"
        journal.write_text('{"seq":1,"lane":"Games","type":"task.started","text":"D02-01"}\n')
        from ops.control_gateway.biella_control_runner import ProductionJournalTailer
        tailer = ProductionJournalTailer(journal, self.publish, poll_seconds=0.01)
        tailer.start()
        import time
        deadline = time.time() + 1
        while time.time() < deadline and not any(event[1].get("type") == "task.started" for event in self.events):
            time.sleep(0.01)
        tailer.stop()
        self.assertTrue(any(event[0] == "Games" and event[1].get("text") == "D02-01" for event in self.events))


    def test_games_standalone_dialog_shares_production_run_lock(self):
        import fcntl
        runtime = Path(self.tmp.name) / "prod" / "runtime.json"
        runtime.parent.mkdir()
        lock_path = runtime.parent / "run.lock"
        handle = lock_path.open("a+")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            runner = ProjectRunner(
                lane_workdirs={"Website": self.website, "Engine": self.engine, "Games": self.games},
                runtime_env_loader=lambda: {}, exec_command=self.capture, background=lambda fn: fn(),
                production_runtime_path=runtime, production_active=lambda: False,
            )
            with self.assertRaisesRegex(Exception, "production or dialog active"):
                runner.start_dialog("Games", "standalone", self.publish)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


if __name__ == "__main__":
    unittest.main()
