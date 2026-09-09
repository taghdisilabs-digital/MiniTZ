from __future__ import annotations

import base64
from collections import deque
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
    def __init__(self, history_limit: int = 500):
        self._subscribers: dict[str, list[queue.Queue]] = {lane: [] for lane in LANES}
        self._history: dict[str, deque] = {lane: deque(maxlen=history_limit) for lane in LANES}
        self._next_id: dict[str, int] = {lane: 1 for lane in LANES}
        self._lock = threading.Lock()

    def subscribe(self, lane: str) -> queue.Queue:
        channel: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._subscribers[lane].append(channel)
        return channel

    def subscribe_with_replay(self, lane: str, after_id: int = 0) -> tuple[queue.Queue, list[dict[str, object]]]:
        channel: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            replay = [dict(item) for item in self._history[lane] if int(item.get("event_id", 0)) > after_id]
            self._subscribers[lane].append(channel)
        return channel, replay

    def replay(self, lane: str, after_id: int = 0) -> list[dict[str, object]]:
        with self._lock:
            return [dict(item) for item in self._history[lane] if int(item.get("event_id", 0)) > after_id]

    def unsubscribe(self, lane: str, channel: queue.Queue) -> None:
        with self._lock:
            if channel in self._subscribers[lane]:
                self._subscribers[lane].remove(channel)

    def publish(self, lane: str, event: dict[str, object]) -> None:
        with self._lock:
            event_id = self._next_id[lane]
            self._next_id[lane] += 1
            event["event_id"] = event_id
            recorded = dict(event)
            self._history[lane].append(recorded)
            targets = list(self._subscribers.get(lane, []))
        for target in targets:
            try:
                target.put_nowait(dict(recorded))
            except queue.Full:
                pass


class ControlHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, *, static_root, auth_store, sessions, state, assets, events, live=None, live_by_host=None):
        super().__init__(address, handler)
        self.static_root = Path(static_root).resolve()
        self.auth_store = auth_store
        self.sessions = sessions
        self.state = state
        self.assets = assets
        self.events = events
        self.live = live
        self.live_by_host = {str(host).lower(): projection for host, projection in (live_by_host or {}).items()}


class ControlHandler(BaseHTTPRequestHandler):
    server_version = "BiellaControl/1"

    def log_message(self, fmt, *args):
        print("control", self.address_string(), fmt % args)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'")
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


    def _stream_file(self, candidate: Path, *, cache_control: str, disposition: str | None = None) -> None:
        try:
            size = candidate.stat().st_size
        except OSError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "asset_not_found"})
            return
        start = 0
        end = max(0, size - 1)
        status = HTTPStatus.OK
        raw_range = self.headers.get("Range", "").strip()
        if raw_range:
            if not raw_range.startswith("bytes=") or "," in raw_range:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            spec = raw_range[6:]
            left, sep, right = spec.partition("-")
            if not sep:
                left = right = ""
            try:
                if left:
                    start = int(left)
                    end = int(right) if right else end
                elif right:
                    count = int(right)
                    start = max(0, size - count)
                else:
                    raise ValueError
            except ValueError:
                start = size
            if start < 0 or start >= size or end < start:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            end = min(end, size - 1)
            status = HTTPStatus.PARTIAL_CONTENT
        length = max(0, end - start + 1) if size else 0
        mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.send_header("Cache-Control", cache_control)
        self._security_headers()
        self.end_headers()
        if length <= 0:
            return
        try:
            with candidate.open("rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = handle.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (OSError, BrokenPipeError, ConnectionResetError):
            return

    def _serve_asset(self, lane: str, root_id: str, relative_path: str) -> None:
        try:
            candidate = self.server.assets.resolve_asset(lane, root_id, relative_path)
        except ValueError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "asset_not_found"})
            return
        self._stream_file(
            candidate, cache_control="private, max-age=60",
            disposition=f'inline; filename="{candidate.name}"',
        )

    def _live_projection(self):
        host = self.headers.get("Host", "").split(":", 1)[0].strip().lower()
        return self.server.live_by_host.get(host, self.server.live)

    def _serve_live_asset(self, root_id: str, relative_path: str) -> None:
        live = self._live_projection()
        if live is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "live_unavailable"})
            return
        try:
            _, candidate = live.resolve_public_asset(root_id, relative_path)
        except (ValueError, OSError):
            self._json(HTTPStatus.NOT_FOUND, {"error": "asset_not_found"})
            return
        self._stream_file(
            candidate, cache_control="public, max-age=15, must-revalidate",
            disposition=f'inline; filename="{candidate.name}"',
        )

    def _handle_live_events(self) -> None:
        live = self._live_projection()
        if live is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "live_unavailable"})
            return
        try:
            after_id = int(self.headers.get("Last-Event-ID", "0") or 0)
        except ValueError:
            after_id = 0
        if hasattr(live, "events_since"):
            self._handle_projection_events(live, after_id)
            return
        lane = "Games"
        channel, replay = self.server.events.subscribe_with_replay(lane, after_id)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self._security_headers()
        self.end_headers()

        def send_event(event: dict[str, object]) -> None:
            safe = live.sanitize_event(event)
            if not safe:
                return
            payload = json.dumps(safe, separators=(",", ":")).encode()
            event_id = int(event.get("event_id", 0) or 0)
            if event_id:
                self.wfile.write(f"id: {event_id}\n".encode())
            self.wfile.write(b"data: " + payload + b"\n\n")

        try:
            connected = {
                "event_id": 0, "seq": 0, "time": "", "task_id": "",
                "category": "BIELLA", "state": "CONNECTED", "text": "Live stream connected",
            }
            self.wfile.write(b"data: " + json.dumps(connected, separators=(",", ":")).encode() + b"\n\n")
            for event in replay:
                send_event(event)
            self.wfile.flush()
            while True:
                try:
                    send_event(channel.get(timeout=10))
                except queue.Empty:
                    heartbeat = live.heartbeat_event()
                    self.wfile.write(b"data: " + json.dumps(heartbeat, separators=(",", ":")).encode() + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.server.events.unsubscribe(lane, channel)


    def _handle_projection_events(self, live, after_id: int) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self._security_headers()
        self.end_headers()
        cursor = after_id
        last_heartbeat = 0.0
        try:
            connected = {
                "event_id": 0, "seq": 0, "time": "", "task_id": "",
                "category": "MINITZ", "state": "CONNECTED", "text": "MiniTZ live stream connected",
            }
            self.wfile.write(b"data: " + json.dumps(connected, separators=(",", ":")).encode() + b"\n\n")
            self.wfile.flush()
            while True:
                events = live.events_since(cursor)
                for event in events:
                    safe = live.sanitize_event(event)
                    if not safe:
                        continue
                    event_id = int(safe.get("event_id") or 0)
                    if event_id:
                        cursor = max(cursor, event_id)
                        self.wfile.write(f"id: {event_id}\n".encode())
                    self.wfile.write(b"data: " + json.dumps(safe, separators=(",", ":")).encode() + b"\n\n")
                now = time.monotonic()
                if not events and now - last_heartbeat >= 10:
                    heartbeat = live.heartbeat_event()
                    self.wfile.write(b"data: " + json.dumps(heartbeat, separators=(",", ":")).encode() + b"\n\n")
                    last_heartbeat = now
                self.wfile.flush()
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _handle_events(self, lane: str) -> None:
        try:
            after_id = int(self.headers.get("Last-Event-ID", "0") or 0)
        except ValueError:
            after_id = 0
        channel, replay = self.server.events.subscribe_with_replay(lane, after_id)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self._security_headers()
        self.end_headers()

        def send_event(event: dict[str, object]) -> None:
            payload = json.dumps(event, separators=(",", ":")).encode()
            event_id = int(event.get("event_id", 0) or 0)
            if event_id:
                self.wfile.write(f"id: {event_id}\n".encode())
            self.wfile.write(b"data: " + payload + b"\n\n")

        try:
            self.wfile.write(b'data: {"type":"stream.connected","text":"Live stream connected"}\n\n')
            for event in replay:
                send_event(event)
            self.wfile.flush()
            while True:
                try:
                    send_event(channel.get(timeout=15))
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
        if path == "/live-api/snapshot":
            live = self._live_projection()
            if live is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "live_unavailable"})
            else:
                self._json(HTTPStatus.OK, live.snapshot())
            return
        if path == "/live-api/events":
            self._handle_live_events()
            return
        if path == "/live-api/asset":
            query = parse_qs(parsed.query)
            root_id = str((query.get("root_id") or [""])[0])
            relative_path = str((query.get("path") or [""])[0])
            if not root_id or not relative_path:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_asset_request"})
                return
            self._serve_live_asset(root_id, relative_path)
            return
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
        if path == "/v1/control/assets":
            if not self._require_session():
                return
            query = parse_qs(parsed.query)
            lane = self._lane((query.get("lane") or [""])[0])
            if not lane:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_lane"})
                return
            kind = (query.get("kind") or [None])[0]
            source_class = (query.get("source_class") or [None])[0]
            try:
                limit = int((query.get("limit") or ["100"])[0])
                payload = self.server.assets.list_assets(lane, kind=kind, source_class=source_class, limit=limit)
            except (TypeError, ValueError):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_asset_query"})
                return
            self._json(HTTPStatus.OK, payload)
            return
        if path == "/v1/control/assets/file":
            if not self._require_session():
                return
            query = parse_qs(parsed.query)
            lane = self._lane((query.get("lane") or [""])[0])
            root_id = str((query.get("root_id") or [""])[0])
            relative_path = str((query.get("path") or [""])[0])
            if not lane or not root_id or not relative_path:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_asset_request"})
                return
            self._serve_asset(lane, root_id, relative_path)
            return
        route_map = {
            "/v1/control/projection": "projection",
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
        if path.startswith("/live-api/"):
            self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "live_api_read_only"})
            return
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
        if path in {"/v1/control/dialog", "/v1/control/runs"}:
            if not self._require_session():
                return
            self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "control_read_only"})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})


def build_server(*, host: str, port: int, static_root: Path, auth_store: AuthStore,
                 sessions: SessionStore, state, assets, events: EventHub, live=None, live_by_host=None) -> ControlHTTPServer:
    return ControlHTTPServer(
        (host, port), ControlHandler,
        static_root=static_root,
        auth_store=auth_store,
        sessions=sessions,
        state=state,
        assets=assets,
        events=events,
        live=live,
        live_by_host=live_by_host,
    )
