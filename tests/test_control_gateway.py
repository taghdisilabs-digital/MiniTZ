from __future__ import annotations

import http.client
import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path

from ops.control_gateway.biella_control_gateway import (
    AuthStore,
    EventHub,
    SessionStore,
    build_server,
    password_record,
)


class FakeState:
    def payload(self, route: str, lane: str):
        if route == "overview":
            return {"lane": lane, "goal": "current goal", "active_task": "current task", "status": "READY"}
        return {"lane": lane, "items": []}


class FakeRunner:
    def __init__(self):
        self.dialog_calls = []
        self.run_calls = []

    def start_dialog(self, lane, message, publish):
        self.dialog_calls.append((lane, message))
        publish(lane, {"text": "accepted"})
        return "dialog-1"

    def run_capability(self, lane, capability_id, auto_run, publish):
        self.run_calls.append((lane, capability_id, auto_run))
        return {"run_id": "run-1", "status": "COMPLETE"}


class FakeLive:
    def __init__(self, preview: Path):
        self.preview = preview

    def snapshot(self):
        return {"schema": "biella.public_live_snapshot/v1", "connection": {"state": "LIVE"}, "production": {"task_id": "D03-01"}}

    def resolve_public_asset(self, root_id, relative_path):
        if root_id != "test" or relative_path != "preview.png":
            raise ValueError("asset unavailable")
        return "Games", self.preview

    @staticmethod
    def sanitize_event(event):
        return dict(event)

    @staticmethod
    def heartbeat_event():
        return {"category": "BIELLA", "state": "HEARTBEAT", "text": "heartbeat"}


class FakeAssets:
    def __init__(self, preview: Path):
        self.preview = preview

    def list_assets(self, lane, **kwargs):
        return {"lane": lane, "count": 1, "items": [{
            "lane": lane, "root_id": "test", "path": "preview.png",
            "name": "preview.png", "kind": "image", "source_class": "CURRENT",
            "previewable": True, "size_bytes": self.preview.stat().st_size,
        }]}

    def resolve_asset(self, lane, root_id, relative_path):
        if lane != "Games" or root_id != "test" or relative_path != "preview.png":
            raise ValueError("asset unavailable")
        return self.preview


class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        static = root / "site"
        (static / "control").mkdir(parents=True)
        (static / "control" / "index.html").write_text("<html>control</html>")
        (static / "data").mkdir()
        (static / "data" / "control-runtime.json").write_text('{"api_base":"/v1/control"}')
        auth_file = root / "auth.json"
        auth_file.write_text(json.dumps({
            "schema": "biella-control-auth/v1",
            "users": {
                "mahdi": password_record("operator-pass", "operator"),
                "patrick": password_record("observer-pass", "observer"),
            },
        }))
        auth_file.chmod(0o600)
        self.runner = FakeRunner()
        self.preview = root / "preview.png"
        self.preview.write_bytes(b"\x89PNG\r\npreview")
        self.assets = FakeAssets(self.preview)
        self.live = FakeLive(self.preview)
        self.server = build_server(
            host="127.0.0.1",
            port=0,
            static_root=static,
            auth_store=AuthStore(auth_file),
            sessions=SessionStore(ttl_seconds=3600),
            state=FakeState(),
            runner=self.runner,
            assets=self.assets,
            events=EventHub(),
            live=self.live,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def request(self, method, path, body=None, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(body)
        if cookie:
            headers["Cookie"] = cookie
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        parsed = json.loads(raw) if raw and response.getheader("Content-Type", "").startswith("application/json") else raw
        result = response.status, response.getheaders(), parsed
        conn.close()
        return result

    def login(self, username, password):
        status, headers, body = self.request("POST", "/v1/control/session", {"username": username, "password": password})
        self.assertEqual(status, 200)
        cookie = next(value for key, value in headers if key.lower() == "set-cookie")
        return cookie.split(";", 1)[0], body

    def test_static_control_and_session_bootstrap(self):
        status, _, body = self.request("GET", "/")
        self.assertEqual(status, 302)
        status, _, body = self.request("GET", "/control/")
        self.assertEqual(status, 200)
        self.assertIn(b"control", body)
        status, _, body = self.request("GET", "/v1/control/session")
        self.assertEqual(status, 200)
        self.assertFalse(body["authenticated"])

    def test_operator_login_sets_secure_cookie(self):
        cookie, body = self.login("mahdi", "operator-pass")
        self.assertEqual(body["session"]["role"], "operator")
        status, headers, _ = self.request("POST", "/v1/control/session", {"username": "mahdi", "password": "operator-pass"})
        value = next(value for key, value in headers if key.lower() == "set-cookie")
        self.assertIn("HttpOnly", value)
        self.assertIn("Secure", value)
        self.assertIn("SameSite=Strict", value)
        self.assertTrue(cookie.startswith("biella_control_session="))

    def test_observer_cannot_write(self):
        cookie, _ = self.login("patrick", "observer-pass")
        status, _, body = self.request("POST", "/v1/control/dialog", {"lane": "Engine", "message": "hello"}, cookie)
        self.assertEqual(status, 403)
        status, _, body = self.request("POST", "/v1/control/runs", {"lane": "Engine", "capability_id": "workstation.status"}, cookie)
        self.assertEqual(status, 403)

    def test_operator_can_read_and_run_only_approved_capabilities(self):
        cookie, _ = self.login("mahdi", "operator-pass")
        status, _, body = self.request("GET", "/v1/control/overview?lane=Engine", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(body["lane"], "Engine")
        status, _, body = self.request("POST", "/v1/control/runs", {"lane": "Engine", "capability_id": "workstation.status", "auto_run": True}, cookie)
        self.assertEqual(status, 200)
        self.assertEqual(body["run_id"], "run-1")
        status, _, body = self.request("POST", "/v1/control/runs", {"lane": "Engine", "capability_id": "shell.exec"}, cookie)
        self.assertEqual(status, 400)

    def test_invalid_lane_and_generic_command_route_are_rejected(self):
        cookie, _ = self.login("mahdi", "operator-pass")
        status, _, body = self.request("GET", "/v1/control/overview?lane=Legacy", cookie=cookie)
        self.assertEqual(status, 400)
        status, _, body = self.request("POST", "/v1/control/command", {"command": "id"}, cookie)
        self.assertEqual(status, 404)

    def test_operator_dialog_is_project_scoped(self):
        cookie, _ = self.login("mahdi", "operator-pass")
        status, _, body = self.request("POST", "/v1/control/dialog", {"lane": "Website", "message": "inspect current source"}, cookie)
        self.assertEqual(status, 202)
        self.assertEqual(body["dialog_id"], "dialog-1")
        self.assertEqual(self.runner.dialog_calls, [("Website", "inspect current source")])

    def test_public_live_snapshot_and_asset_are_read_only_without_control_auth(self):
        status, _, body = self.request("GET", "/live-api/snapshot")
        self.assertEqual(status, 200)
        self.assertEqual(body["connection"]["state"], "LIVE")
        self.assertEqual(body["production"]["task_id"], "D03-01")
        status, headers, body = self.request("GET", "/live-api/asset?root_id=test&path=preview.png")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"\x89PNG\r\npreview")
        self.assertTrue(any(k.lower() == "content-type" and v == "image/png" for k, v in headers))
        status, _, body = self.request("GET", "/live-api/asset?root_id=test&path=../secret")
        self.assertEqual(status, 404)

    def test_public_live_api_rejects_writes(self):
        status, _, body = self.request("POST", "/live-api/snapshot", {"anything": "ignored"})
        self.assertEqual(status, 405)
        self.assertEqual(body["error"], "live_api_read_only")

    def test_assets_require_auth_and_return_allowlisted_preview(self):
        status, _, body = self.request("GET", "/v1/control/assets?lane=Games")
        self.assertEqual(status, 401)
        cookie, _ = self.login("mahdi", "operator-pass")
        status, _, body = self.request("GET", "/v1/control/assets?lane=Games&limit=20", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(body["items"][0]["name"], "preview.png")
        status, headers, body = self.request(
            "GET", "/v1/control/assets/file?lane=Games&root_id=test&path=preview.png", cookie=cookie
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, b"\x89PNG\r\npreview")
        self.assertTrue(any(k.lower() == "content-type" and v == "image/png" for k, v in headers))

    def test_asset_preview_rejects_unknown_path(self):
        cookie, _ = self.login("mahdi", "operator-pass")
        status, _, body = self.request(
            "GET", "/v1/control/assets/file?lane=Games&root_id=test&path=../secret", cookie=cookie
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()


class EventHubTest(unittest.TestCase):
    def test_publish_subscribe_is_lane_scoped(self):
        hub = EventHub()
        website = hub.subscribe("Website")
        engine = hub.subscribe("Engine")
        event = {"text": "current event"}
        hub.publish("Website", event)
        self.assertEqual(website.get(timeout=1), event)
        with self.assertRaises(queue.Empty):
            engine.get(timeout=0.05)
        hub.unsubscribe("Website", website)
        hub.unsubscribe("Engine", engine)

    def test_event_hub_assigns_ids_and_replays_after_cursor(self):
        hub = EventHub()
        hub.publish("Games", {"type":"task.started","text":"D02-01"})
        hub.publish("Games", {"type":"tool.started","text":"Unreal"})
        replay = hub.replay("Games", after_id=1)
        self.assertEqual(len(replay), 1)
        self.assertEqual(replay[0]["event_id"], 2)
        self.assertEqual(replay[0]["type"], "tool.started")
