#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

try:
    from .minitz_control_assets import AssetCatalog, AssetRoot
    from .minitz_control_gateway import AuthStore, EventHub, SessionStore, build_server
    from .minitz_base_projection import LiveProjection
    from .minitz_live_projection import MiniTZLiveProjection
    from .minitz_control_runner import ProductionJournalTailer
    from .minitz_control_state import WorkstationState
except ImportError:
    from minitz_control_assets import AssetCatalog, AssetRoot
    from minitz_control_gateway import AuthStore, EventHub, SessionStore, build_server
    from minitz_base_projection import LiveProjection
    from minitz_live_projection import MiniTZLiveProjection
    from minitz_control_runner import ProductionJournalTailer
    from minitz_control_state import WorkstationState


def main() -> int:
    host = os.environ.get("MINITZ_CONTROL_HOST", "127.0.0.1")
    port = int(os.environ.get("MINITZ_CONTROL_PORT", "8787"))
    static_root = Path(os.environ.get("MINITZ_CONTROL_STATIC_ROOT", "/root/attached-storage/minitz-os-sandbox/state/control/site"))
    auth_file = Path(os.environ.get("MINITZ_CONTROL_AUTH_FILE", "/root/attached-storage/minitz-os-sandbox/state/credentials/control/auth.json"))
    repo = Path(os.environ.get("MINITZ_CONTROL_REPO", "/root/attached-storage/minitz-os-sandbox/workspace/repo"))
    games_project = repo / "projects" / "minitz-games"
    website_project = repo / "website"
    ttl = int(os.environ.get("MINITZ_CONTROL_SESSION_TTL", "28800"))
    production_runtime_root = Path(os.environ.get("MINITZ_RUNTIME_ROOT", "/root/attached-storage/minitz-os-sandbox/state/production"))

    if not static_root.is_dir():
        raise SystemExit(f"control static root is missing: {static_root}")

    events = EventHub()
    state = WorkstationState(repo=repo)
    asset_catalog = AssetCatalog({
        "Website": [
            AssetRoot("website-generated", repo / "state-artifacts" / "website", "GENERATED_DRAFT"),
            AssetRoot("website-build", website_project / "dist", "CURRENT_BUILD"),
        ],
        "Engine": [
            AssetRoot("engine-generated", repo / "state-artifacts" / "engine", "GENERATED_DRAFT"),
            AssetRoot("engine-builds", Path("/root/attached-storage/minitz-os-sandbox/state/builds"), "CURRENT_BUILD"),
        ],
        "Games": [
            AssetRoot("games-presentation", games_project / "Build" / "Presentation", "TASK_EVIDENCE"),
            AssetRoot("games-aaa", games_project / "Build" / "AAA", "TASK_EVIDENCE"),
            AssetRoot("games-unreal-screenshots", games_project / "Saved" / "Screenshots", "UNREAL_CAPTURE"),
            AssetRoot("games-generated", repo / "state-artifacts" / "games", "GENERATED_DRAFT"),
            AssetRoot("games-visual-output", games_project / "visual_production" / "outputs", "GENERATED_DRAFT"),
            AssetRoot("games-content", games_project / "Content", "CURRENT_SOURCE"),
        ],
    })
    live = LiveProjection(repo=repo, runtime_root=production_runtime_root, assets=asset_catalog)
    minitz_live = MiniTZLiveProjection(repo=repo, runtime_root=production_runtime_root, assets=asset_catalog, analysis_root=Path("/root/attached-storage/minitz-os-sandbox/state/task-program"))

    def publish(lane: str, event: dict[str, object]) -> None:
        events.publish(lane, event)
        if lane == "Games":
            live.observe_event(event)

    live.start()
    minitz_live.start()
    journal_tailer = ProductionJournalTailer(production_runtime_root / "events.jsonl", publish)
    journal_tailer.start()

    server = build_server(
        host=host,
        port=port,
        static_root=static_root,
        auth_store=AuthStore(auth_file),
        sessions=SessionStore(ttl_seconds=ttl),
        state=state,
        assets=asset_catalog,
        events=events,
        live=live,
        live_by_host={"minitz.taghdisilabs.digital": minitz_live},
    )
    print(f"MiniTZ control gateway listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        journal_tailer.stop()
        minitz_live.stop()
        live.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
