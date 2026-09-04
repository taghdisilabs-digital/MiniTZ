from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import queue
import secrets
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

LANES = ("Website", "Engine", "Games")
SESSION_COOKIE = "biella_control_session"
APPROVED_CAPABILITIES = {
    "workstation.status",
    "workstation.doctor",
    "providers.check",
    "git.status.current",
}


def password_record(password: str, role: str) -> dict[str, object]:
    if role not in {"operator", "observer"}:
        raise ValueError("invalid role")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return {
        "role": role,
        "algorithm": "scrypt",
        "n": 16384,
        "r": 8,
        "p": 1,
        "salt": base64.b64encode(salt).decode(),
        "hash": base64.b64encode(digest).decode(),
    }


class AuthStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def configured(self) -> bool:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return False
        return isinstance(data.get("users"), dict) and bool(data["users"])

    def verify(self, username: str, password: str) -> str | None:
        try:
            data = json.loads(self.path.read_text())
            record = data["users"][username]
            salt = base64.b64decode(record["salt"])
            expected = base64.b64decode(record["hash"])
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            return None
        actual = hashlib.scrypt(
            password.encode(), salt=salt,
            n=int(record.get("n", 16384)), r=int(record.get("r", 8)), p=int(record.get("p", 1)), dklen=len(expected),
        )
        if not hmac.compare_digest(actual, expected):
            return None
        role = str(record.get("role", ""))
        return role if role in {"operator", "observer"} else None


@dataclass(frozen=True)
class Session:
    username: str
    role: str
    expires_at: float


class SessionStore:
    def __init__(self, ttl_seconds: int = 28800):
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, username: str, role: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._items[token] = Session(username, role, time.time() + self.ttl_seconds)
        return token

    def get(self, token: str | None) -> Session | None:
        if not token:
            return None
        with self._lock:
            session = self._items.get(token)
            if session and session.expires_at > time.time():
                return session
            self._items.pop(token, None)
        return None

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._items.pop(token, None)


class EventHub:
    def __init__(self):
        self._subscribers: dict[str, list[queue.Queue]] = {lane: [] for lane in LANES}
        self._lock = threading.Lock()

    def subscribe(self, lane: str) -> queue.Queue:
        channel: queue.Queue = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers[lane].append(channel)
        return channel

    def unsubscribe(self, lane: str, channel: queue.Queue) -> None:
        with self._lock:
            if channel in self._subscribers[lane]:
                self._subscribers[lane].remove(channel)

    def publish(self, lane: str, event: dict[str, object]) -> None:
        with self._lock:
            targets = list(self._subscribers.get(lane, []))
        for target in targets:
            try:
                target.put_nowait(event)
            except queue.Full:
                pass


class ControlHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, *, static_root, auth_store, sessions, state, runner, events):
        super().__init__(address, handler)
        self.static_root = Path(static_root).resolve()
        self.auth_store = auth_store
        self.sessions = sessions
        self.state = state
        self.runner = runner
        self.events = events


class ControlHandler(BaseHTTPRequestHandler):
    server_version = "BiellaControl/1"

    def log_message(self, fmt, *args):
        print("control", self.address_string(), fmt % args)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'")
    def _json(self, status: int, payload: object, extra_headers: list[tuple[str, str]] | None = None) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 1024 * 1024:
            return {}
        try:
            parsed = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _cookie_token(self) -> str | None:
        raw = self.headers.get("Cookie", "")
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
        except Exception:
            return None
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def _session(self) -> Session | None:
        return self.server.sessions.get(self._cookie_token())
    def _require_session(self, write: bool = False) -> Session | None:
        session = self._session()
        if not session:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication_required"})
            return None
        if write and session.role != "operator":
            self._json(HTTPStatus.FORBIDDEN, {"error": "operator_required"})
            return None
        return session

    @staticmethod
    def _lane(value: object) -> str | None:
        lane = str(value or "")
        return lane if lane in LANES else None

    def _lane_from_query(self) -> str | None:
        query = parse_qs(urlparse(self.path).query)
        return self._lane((query.get("lane") or [""])[0])

    def _serve_static(self, request_path: str) -> None:
        if request_path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/control/")
            self._security_headers()
            self.end_headers()
            return
        relative = unquote(request_path.lstrip("/"))
        if request_path.endswith("/"):
            relative += "index.html"
        candidate = (self.server.static_root / relative).resolve()
        try:
            candidate.relative_to(self.server.static_root)
        except ValueError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not candidate.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        body = candidate.read_bytes()
        mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if candidate.name.endswith(".json") else "private, max-age=300")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _handle_events(self, lane: str) -> None:
        channel = self.server.events.subscribe(lane)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self._security_headers()
        self.end_headers()
        try:
            self.wfile.write(b'data: {"text":"Live stream connected"}\n\n')
            self.wfile.flush()
            while True:
                try:
                    event = channel.get(timeout=15)
                    payload = json.dumps(event, separators=(",", ":")).encode()
                    self.wfile.write(b"data: " + payload + b"\n\n")
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.server.events.unsubscribe(lane, channel)
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/v1/control/session":
            session = self._session()
            if not session:
                self._json(HTTPStatus.OK, {"authenticated": False, "auth_configured": self.server.auth_store.configured()})
            else:
                self._json(HTTPStatus.OK, {"authenticated": True, "username": session.username, "role": session.role})
            return
        if path == "/v1/control/events":
            if not self._require_session():
                return
            lane = self._lane_from_query()
            if not lane:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_lane"})
                return
            self._handle_events(lane)
            return
        route_map = {
            "/v1/control/overview": "overview",
            "/v1/control/capabilities": "capabilities",
            "/v1/control/services": "services",
            "/v1/control/milestones": "milestones",
            "/v1/control/hardware": "hardware",
            "/v1/control/workers": "workers",
            "/v1/control/files": "files",
        }
        if path in route_map:
            if not self._require_session():
                return
            lane = self._lane_from_query()
            if not lane:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_lane"})
                return
            self._json(HTTPStatus.OK, self.server.state.payload(route_map[path], lane))
            return
        self._serve_static(path)
    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/v1/control/session":
            body = self._read_json()
            username = str(body.get("username", ""))
            password = str(body.get("password", ""))
            if not self.server.auth_store.configured():
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "auth_not_configured"})
                return
            role = self.server.auth_store.verify(username, password)
            if not role:
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "invalid_credentials"})
                return
            token = self.server.sessions.create(username, role)
            cookie = f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={self.server.sessions.ttl_seconds}"
            self._json(HTTPStatus.OK, {"session": {"username": username, "role": role}}, [("Set-Cookie", cookie)])
            return
        if path == "/v1/control/session/logout":
            token = self._cookie_token()
            self.server.sessions.revoke(token)
            cookie = f"{SESSION_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0"
            self._json(HTTPStatus.OK, {"logged_out": True}, [("Set-Cookie", cookie)])
            return
        if path == "/v1/control/dialog":
            if not self._require_session(write=True):
                return
            body = self._read_json()
            lane = self._lane(body.get("lane"))
            message = str(body.get("message", "")).strip()
            if not lane or not message or len(message) > 12000:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_dialog"})
                return
            dialog_id = self.server.runner.start_dialog(lane, message, self.server.events.publish)
            self._json(HTTPStatus.ACCEPTED, {"dialog_id": dialog_id, "status": "ACCEPTED"})
            return
        if path == "/v1/control/runs":
            if not self._require_session(write=True):
                return
            body = self._read_json()
            lane = self._lane(body.get("lane"))
            capability_id = str(body.get("capability_id", ""))
            auto_run = bool(body.get("auto_run", False))
            if not lane or capability_id not in APPROVED_CAPABILITIES:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "unapproved_capability"})
                return
            result = self.server.runner.run_capability(lane, capability_id, auto_run, self.server.events.publish)
            self._json(HTTPStatus.OK, result)
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})


def build_server(*, host: str, port: int, static_root: Path, auth_store: AuthStore,
                 sessions: SessionStore, state, runner, events: EventHub) -> ControlHTTPServer:
    return ControlHTTPServer(
        (host, port), ControlHandler,
        static_root=static_root,
        auth_store=auth_store,
        sessions=sessions,
        state=state,
        runner=runner,
        events=events,
    )
