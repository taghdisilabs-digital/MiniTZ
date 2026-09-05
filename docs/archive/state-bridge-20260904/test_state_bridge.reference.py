from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ops.state_bridge.biella_state_bridge import (
    CommandResult,
    StateBridge,
    StateBridgeError,
    load_registry,
)


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], CommandResult]):
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv, cwd=None, timeout=30):
        key = tuple(argv)
        self.calls.append(key)
        return self.responses.get(key, CommandResult(1, b"", b"missing fake command"))


def result(text: str, code: int = 0) -> CommandResult:
    return CommandResult(code, text.encode(), b"")


class StateBridgeTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs/project-state").mkdir(parents=True)
        self.engine = self.root / "engine"
        self.website = self.root / "website"
        self.games = self.root / "games"
        for path in (self.engine, self.website, self.games):
            path.mkdir()
        (self.root / "docs/project-state/03_BIELLA_CURRENT_STATE.md").write_text(
            "# state\n\n```yaml\nschema: biella.current_state/v5\n"
            "numbered_execution:\n  active_prompt: P4-06\n  active_drive_prompt_id: prompt-drive-id\n"
            "continuation:\n  active_task_id: ENG-P4-06\n  active_task_title: Recipe Learning\n"
            "  ledger_state: READY_ELIGIBLE\n  execution_started: false\n  execution_authorized: true\n```\n"
        )
        (self.root / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").write_text(
            "# task\n\n```yaml\nschema: biella.active_task/v6\n"
            "program_boundary:\n  active_numbered_prompt: P4-06\n  active_prompt_drive_id: prompt-drive-id\n"
            "active_frontier:\n  ledger_task_id: ENG-P4-06\n  title: Recipe Learning\n"
            "  ledger_state: READY_ELIGIBLE\n  execution_started: false\n```\n"
        )
        self.registry = {
            "schema": "biella.state_bridge.sources/v1",
            "lanes": {
                "Engine": {"repo": "patrickminitz-web/biella-engine", "branch": "main", "workdir": str(self.engine)},
                "Website": {"repo": "patrickminitz-web/biella-engine", "branch": "website", "workdir": str(self.website)},
                "Games": {"repo": "patrickminitz-web/biella-games", "branch": "main", "workdir": str(self.games)},
            },
            "drive": {
                "remote": "gdrive",
                "root_id": "root-id",
                "targets": {
                    "current_state": {"path": "20_CURRENT_STATE/03_BIELLA_CURRENT_STATE.md", "id": "state-id", "source": "docs/project-state/03_BIELLA_CURRENT_STATE.md"},
                    "active_task": {"path": "30_EXECUTION/04_BIELLA_ACTIVE_TASK.md", "id": "task-id", "source": "docs/project-state/04_BIELLA_ACTIVE_TASK.md"},
                    "context_index": {"path": "00_START_HERE/BIELLA_PROJECT_CONTEXT_INDEX_CURRENT_2026-09-04.md", "id": "index-id"},
                    "manifest": {"path": "20_CURRENT_STATE/BIELLA_CURRENT_STATE_MANIFEST.json", "id": "manifest-id"},
                },
            },
            "control_url": "https://control.biellagames.dev/control/",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def git_responses(self):
        responses: dict[tuple[str, ...], CommandResult] = {}
        lanes = {
            str(self.engine): ("eng-local", "eng-tree", "eng-local", "main"),
            str(self.website): ("web-local", "web-tree", "web-remote", "control-live"),
            str(self.games): ("game-local", "game-tree", "game-local", "main"),
        }
        for path, (head, tree, remote, branch) in lanes.items():
            responses[("git", "-C", path, "rev-parse", "HEAD")] = result(head + "\n")
            responses[("git", "-C", path, "rev-parse", "HEAD^{tree}")] = result(tree + "\n")
            responses[("git", "-C", path, "branch", "--show-current")] = result(branch + "\n")
            responses[("git", "-C", path, "status", "--porcelain")] = result("")
            canonical = "website" if path == str(self.website) else "main"
            responses[("git", "-C", path, "rev-parse", f"origin/{canonical}")] = result(remote + "\n")
        return responses


class StateBridgeManifestTest(StateBridgeTestBase):
    def test_manifest_has_current_lanes_task_services_and_drive_ids(self):
        responses = self.git_responses()
        responses[("git", "-C", str(self.website), "merge-base", "--is-ancestor", "origin/website", "HEAD")] = result("")
        for service in ("biella-ollama.service", "biella-control-gateway.service", "biella-control-tunnel.service"):
            responses[("systemctl", "is-active", service)] = result("active\n")
        bridge = StateBridge(
            repo_root=self.root,
            registry=self.registry,
            runner=FakeRunner(responses),
            lane_workdirs={"Engine": self.engine, "Website": self.website, "Games": self.games},
            offline=True,
            now=lambda: "2026-09-04T20:45:00Z",
        )
        manifest = bridge.build_manifest()
        self.assertEqual(manifest["schema"], "biella.current_manifest/v1")
        self.assertEqual(manifest["lanes"]["Engine"]["sync_status"], "MATCH")
        self.assertEqual(manifest["lanes"]["Website"]["sync_status"], "AHEAD")
        self.assertEqual(manifest["lanes"]["Games"]["commit"], "game-local")
        self.assertEqual(manifest["active_task"]["id"], "ENG-P4-06")
        self.assertEqual(manifest["active_task"]["prompt_drive_id"], "prompt-drive-id")
        self.assertEqual(manifest["services"]["control_tunnel"], "active")
        self.assertEqual(manifest["drive"]["targets"]["current_state"]["id"], "state-id")
        self.assertEqual(manifest["control_url"], "https://control.biellagames.dev/control/")

    def test_mismatched_current_state_and_active_task_fails(self):
        task = self.root / "docs/project-state/04_BIELLA_ACTIVE_TASK.md"
        task.write_text(task.read_text().replace("ENG-P4-06", "ENG-P4-07").replace("active_numbered_prompt: P4-06", "active_numbered_prompt: P4-07"))
        bridge = StateBridge(repo_root=self.root, registry=self.registry, runner=FakeRunner(self.git_responses()), offline=True)
        with self.assertRaises(StateBridgeError):
            bridge.build_manifest()

    def test_load_registry_requires_exact_canonical_ids(self):
        path = self.root / "registry.json"
        broken = json.loads(json.dumps(self.registry))
        broken["drive"]["targets"]["current_state"]["id"] = ""
        path.write_text(json.dumps(broken))
        with self.assertRaises(StateBridgeError):
            load_registry(path)
