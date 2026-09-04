#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

try:
    from .biella_control_gateway import AuthStore, EventHub, SessionStore, build_server
    from .biella_control_runner import ProjectRunner
    from .biella_control_state import WorkstationState
except ImportError:
    from biella_control_gateway import AuthStore, EventHub, SessionStore, build_server
    from biella_control_runner import ProjectRunner
    from biella_control_state import WorkstationState


def main() -> int:
    host = os.environ.get("BIELLA_CONTROL_HOST", "127.0.0.1")
    port = int(os.environ.get("BIELLA_CONTROL_PORT", "8787"))
    static_root = Path(os.environ.get("BIELLA_CONTROL_STATIC_ROOT", "/var/lib/biella-control/site"))
    auth_file = Path(os.environ.get("BIELLA_CONTROL_AUTH_FILE", "/root/.config/biella-control/auth.json"))
    engine_repo = Path(os.environ.get("BIELLA_CONTROL_ENGINE_REPO", "/root/biella/repos/biella-engine"))
    games_repo = Path(os.environ.get("BIELLA_CONTROL_GAMES_REPO", "/root/biella/repos/biella-games"))
    website_workdir = Path(os.environ.get("BIELLA_CONTROL_WEBSITE_WORKDIR", "/root/biella/worktrees/biella-control-live"))
    website_ref = os.environ.get("BIELLA_CONTROL_WEBSITE_REF", "origin/website")
    ttl = int(os.environ.get("BIELLA_CONTROL_SESSION_TTL", "28800"))

    if not static_root.is_dir():
        raise SystemExit(f"control static root is missing: {static_root}")

    events = EventHub()
    state = WorkstationState(engine_repo=engine_repo, games_repo=games_repo, website_ref=website_ref)
    runner = ProjectRunner(lane_workdirs={
        "Website": website_workdir,
        "Engine": engine_repo,
        "Games": games_repo,
    })

    server = build_server(
        host=host,
        port=port,
        static_root=static_root,
        auth_store=AuthStore(auth_file),
        sessions=SessionStore(ttl_seconds=ttl),
        state=state,
        runner=runner,
        events=events,
    )
    print(f"Biella control gateway listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
