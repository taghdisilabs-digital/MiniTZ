"""MiniTZ sandbox attachments using existing control and coder interfaces.

Read projections are not task authority. Coder protocol attachment never starts
inference or chooses a project/task; the single task controller owns execution.
"""
from __future__ import annotations
import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT / "ops/local-ai", ROOT / "ops/workstation", ROOT / "ops/control_gateway"):
    sys.path.insert(0, str(path))
import minitz_task_program as tasks
import minitz_local_quality as quality
from biella_control_gateway import AuthStore, SessionStore, EventHub, build_server
from biella_control_assets import AssetCatalog
from minitz_live_projection import MiniTZLiveProjection


class SandboxControlState:
    def __init__(self, repo, startup, *, program_reader=tasks.load, observer=quality.snapshot):
        self.repo, self.startup = Path(repo), startup
        self.program_reader, self.observer = program_reader, observer

    def payload(self, route, lane):
        program = self.program_reader()
        current = program.get("current_execution") or {}
        task = next((row for row in program.get("tasks", []) if row.get("task_id") == current.get("task_id")), {})
        common = {"product": "MiniTZ OS", "authority": "READ_ONLY_PROJECTION", "progression_mutation": False,
                  "task_id": current.get("task_id"), "task_revision": current.get("task_revision"),
                  "active_task": task.get("title"), "task_status": task.get("status"), "observed_at_epoch": time.time()}
        if route == "hardware":
            return {**common, "observation": self.observer()}
        if route in {"overview", "projection"}:
            return {**common, "startup_state": self.startup.get("state", "UNKNOWN"),
                    "coder": self.startup.get("coder", {"state": "NOT_ATTACHED"})}
        if route == "capabilities":
            results = self.startup.get("qualification", {}).get("results", [])
            return {**common, "capabilities": [{"id": row.get("case"), "quality": row.get("quality"),
                    "route": row.get("provider"), "cache_reused": row.get("cache_hit")} for row in results]}
        if route == "services":
            return {**common, "services": {"sandbox_control": "RESPONDING", "coder": self.startup.get("coder", {})}}
        if route == "workers":
            return {**common, "workers": task.get("workers", [])}
        if route == "milestones":
            return {**common, "completed": sum(row.get("status") in {"COMPLETE", "COMPLETE_ALREADY"} for row in program.get("tasks", [])),
                    "total": len(program.get("tasks", []))}
        if route == "files":
            return {**common, "source_ref": str(self.repo), "write_scope": task.get("write_scope", {})}
        raise KeyError(route)

    def execute(self, *args, **kwargs):
        raise PermissionError("Use the canonical task executor; a projection cannot grant mutation")


def qualify_coder_protocol(rpc, notify):
    initialized = rpc("initialize", {"clientInfo": {"name": "minitz_os", "title": "MiniTZ OS", "version": "1"}})
    if not isinstance(initialized, dict):
        raise RuntimeError("Invalid coder initialize result")
    notify("initialized")
    configuration = rpc("config/read", {"includeLayers": False})
    if not isinstance(configuration, dict) or not isinstance(configuration.get("config"), dict):
        raise RuntimeError("Coder configuration response is invalid")
    account = rpc("account/read", {"refreshToken": False})
    if not isinstance(account, dict) or "requiresOpenaiAuth" not in account:
        raise RuntimeError("Coder account protocol response is invalid")
    attached = isinstance(account.get("account"), dict)
    required = account.get("requiresOpenaiAuth") is True
    return {"state": "PROTOCOL_AUTH_ATTACHED" if attached else "NEEDS_AUTH" if required else "PROTOCOL_LOCAL_READY",
            "protocol": "initialize/config-read/account-read", "production_turn_started": False,
            "quota_probed": False, "auth_ref_attached": attached,
            "inference_quality": "NOT_EVALUATED", "account_type": (account.get("account") or {}).get("type")}


class CoderTransport:
    def __init__(self, executable, home, log):
        self.messages, self.counter = queue.Queue(), 0
        self.process = subprocess.Popen([str(executable), "app-server", "--listen", "stdio://"],
            cwd=str(ROOT), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
            text=True, bufsize=1, env={**os.environ, "CODEX_HOME": str(home)})
        def read():
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                self.messages.put(message)
            self.messages.put(None)
        threading.Thread(target=read, daemon=True).start()

    def notify(self, method):
        self.process.stdin.write(json.dumps({"method": method}) + "\n")
        self.process.stdin.flush()

    def rpc(self, method, params):
        self.counter += 1
        request_id = self.counter
        self.process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                raise RuntimeError("Coder protocol timeout: " + method) from None
            if message is None:
                raise RuntimeError("Coder protocol closed: " + method)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError("Coder RPC rejected " + method + ": " + str(message["error"].get("code")))
            return message.get("result")
        raise RuntimeError("Coder protocol deadline: " + method)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


def attach_control(startup, *, port=8787):
    static = Path(os.environ.get("MINITZ_CONTROL_STATIC_ROOT", "/resources/control-site"))
    auth = AuthStore(Path(os.environ.get("MINITZ_CONTROL_AUTH_FILE", "/resources/credentials/control-auth.json")))
    if not static.is_dir() or not auth.configured():
        raise RuntimeError("Existing control UI/auth resource is not attached")
    sessions = SessionStore()
    state = SandboxControlState(ROOT, startup)
    assets = AssetCatalog({})
    live = MiniTZLiveProjection(
        repo=ROOT,
        runtime_root=Path(os.environ["BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT"]),
        assets=assets,
        analysis_root=Path(os.environ.get("MINITZ_ANALYSIS_ROOT", "/root/biella/analysis/live_audit")),
        qualification_path=Path(os.environ.get("MINITZ_QUALIFICATION_PATH", "/state/qualification/sandbox-foundation.json")),
    )
    live.start()
    server = None
    token = None
    try:
        server = build_server(
            host="127.0.0.1", port=port, static_root=static, auth_store=auth, sessions=sessions,
            state=state, assets=assets, events=EventHub(),
            live_by_host={"minitz.taghdisilabs.digital": live},
        )
        server.minitz_live_projection = live
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:" + str(server.server_address[1])
        token = sessions.create("minitz-internal-validation", "observer")
        request = urllib.request.Request(base + "/v1/control/overview?lane=Engine",
            headers={"Cookie": "biella_control_session=" + token})
        with urllib.request.urlopen(request, timeout=5) as response:
            actual = json.load(response)
        expected = tasks.load()["current_execution"]["task_id"]
        if actual.get("product") != "MiniTZ OS" or actual.get("task_id") != expected:
            raise RuntimeError("Control projection does not match canonical task")
        live_request = urllib.request.Request(base + "/live-api/snapshot",
            headers={"Host": "minitz.taghdisilabs.digital"})
        with urllib.request.urlopen(live_request, timeout=5) as response:
            live_snapshot = json.load(response)
        production = live_snapshot.get("production") if isinstance(live_snapshot.get("production"), dict) else {}
        if live_snapshot.get("schema") != "minitz.public_live_snapshot/v1" or production.get("task_id") != expected:
            raise RuntimeError("Public MiniTZ live snapshot does not match canonical task")
        try:
            urllib.request.urlopen(base + "/v1/control/overview?lane=Engine", timeout=5)
        except urllib.error.HTTPError as exc:
            if exc.code != 401:
                raise RuntimeError("Unexpected control auth rejection") from None
        else:
            raise RuntimeError("Unauthenticated control request was accepted")
        return server, {"state": "FUNCTIONALLY_ATTACHED", "listen": base, "task_readback": expected,
                        "live_snapshot": "FUNCTIONALLY_ATTACHED",
                        "unauthenticated_access": "DENIED", "progression_mutation": False}
    except Exception:
        if server is not None:
            server.shutdown()
            server.server_close()
        live.stop()
        raise
    finally:
        if token is not None:
            sessions.revoke(token)

