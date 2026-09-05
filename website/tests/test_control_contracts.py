import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL = ROOT / "src" / "control"


class ControlConsoleContractTests(unittest.TestCase):
    def test_control_console_source_exists(self):
        required = [
            CONTROL / "index.html",
            CONTROL / "app.js",
            CONTROL / "styles.css",
            ROOT / "content" / "control-runtime.json",
        ]
        for path in required:
            self.assertTrue(path.is_file(), path)

    def test_control_console_has_four_primary_sections_and_project_contexts(self):
        html = (CONTROL / "index.html").read_text(encoding="utf-8")
        for label in ("Website", "Engine", "Games", "Control", "Work", "Outputs", "System"):
            self.assertIn(label, html)
        for obsolete in ("Live dialog", "Capabilities & Run", "Connected services", "Milestones", "Hardware & API usage", "Running workers", "Current files", "Visuals / Assets"):
            self.assertNotIn(obsolete, html)
        self.assertEqual(html.count('data-view="control"'), 1)
        self.assertEqual(html.count('data-view="work"'), 1)
        self.assertEqual(html.count('data-view="outputs"'), 1)
        self.assertEqual(html.count('data-view="system"'), 1)

    def test_control_console_is_current_gateway_consumer(self):
        app = (CONTROL / "app.js").read_text(encoding="utf-8")
        config = json.loads(
            (ROOT / "content" / "control-runtime.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["schema"], "biella.control-runtime/v1")
        self.assertEqual(config["api_base"], "/v1/control")
        self.assertIn("/session", app)
        self.assertIn("/events", app)
        self.assertNotIn("MiniTZ", app)
        self.assertNotIn("mock", app.lower())


    def test_outputs_view_uses_gateway_asset_api_and_projection(self):
        html = (CONTROL / "index.html").read_text(encoding="utf-8")
        app = (CONTROL / "app.js").read_text(encoding="utf-8")
        css = (CONTROL / "styles.css").read_text(encoding="utf-8")
        self.assertIn('data-view="outputs"', html)
        self.assertIn('/projection?lane=', app)
        self.assertIn('assets?lane=', app)
        self.assertIn('assets/file?lane=', app)
        self.assertIn('asset-grid', css)
        self.assertIn('asset-preview', css)

    def test_control_view_has_automatic_liveness_and_no_fake_active_state(self):
        app = (CONTROL / "app.js").read_text(encoding="utf-8")
        for token in ("ACTIVE", "WAITING", "STALE", "STOPPED", "ERROR", "heartbeat_at", "current_task", "active_model"):
            self.assertIn(token, app)
        self.assertIn("projection", app)

    def test_build_copies_the_private_console(self):
        build = (ROOT / "scripts" / "build.mjs").read_text(encoding="utf-8")
        self.assertIn("src", build)
        self.assertIn("control", build)
        self.assertIn("control-runtime.json", build)


if __name__ == "__main__":
    unittest.main()
