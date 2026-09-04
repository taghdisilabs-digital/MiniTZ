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
        self.server = build_server(
            host="127.0.0.1",
            port=0,
            static_root=static,
            auth_store=AuthStore(auth_file),
            sessions=SessionStore(ttl_seconds=3600),
            state=FakeState(),
            runner=self.runner,
            events=EventHub(),
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
