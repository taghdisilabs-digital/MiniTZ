#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

try:
    from .biella_control_assets import AssetCatalog, AssetRoot
    from .biella_control_gateway import AuthStore, EventHub, SessionStore, build_server
    from .biella_live_projection import LiveProjection
    from .minitz_live_projection import MiniTZLiveProjection
    from .biella_control_runner import ProductionJournalTailer
    from .biella_control_state import WorkstationState
except ImportError:
    from biella_control_assets import AssetCatalog, AssetRoot
    from biella_control_gateway import AuthStore, EventHub, SessionStore, build_server
    from biella_live_projection import LiveProjection
    from minitz_live_projection import MiniTZLiveProjection
    from biella_control_runner import ProductionJournalTailer
    from biella_control_state import WorkstationState


def main() -> int:
    host = os.environ.get("BIELLA_CONTROL_HOST", "127.0.0.1")
    port = int(os.environ.get("BIELLA_CONTROL_PORT", "8787"))
    static_root = Path(os.environ.get("BIELLA_CONTROL_STATIC_ROOT", "/var/lib/biella-control/site"))
    auth_file = Path(os.environ.get("BIELLA_CONTROL_AUTH_FILE", "/root/.config/biella-control/auth.json"))
    repo = Path(os.environ.get("BIELLA_CONTROL_REPO", "/mnt/biella-extra/minitz-os-sandbox/workspace/repo"))
    games_project = repo / "projects" / "biella-games"
    website_project = repo / "website"
    ttl = int(os.environ.get("BIELLA_CONTROL_SESSION_TTL", "28800"))
    production_runtime_root = Path(os.environ.get("BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT", "/mnt/biella-extra/biella-runtime/codex-production"))

    if not static_root.is_dir():
        raise SystemExit(f"control static root is missing: {static_root}")

    events = EventHub()
    state = WorkstationState(repo=repo)
    asset_catalog = AssetCatalog({
        "Website": [
            AssetRoot("website-generated", Path("/root/biella/artifacts/website"), "GENERATED_DRAFT"),
            AssetRoot("website-build", website_project / "dist", "CURRENT_BUILD"),
        ],
        "Engine": [
            AssetRoot("engine-generated", Path("/root/biella/artifacts/engine"), "GENERATED_DRAFT"),
            AssetRoot("engine-builds", Path("/mnt/biella-extra/biella-runtime/builds"), "CURRENT_BUILD"),
        ],
        "Games": [
            AssetRoot("games-presentation", games_project / "Build" / "Presentation", "TASK_EVIDENCE"),
            AssetRoot("games-aaa", games_project / "Build" / "AAA", "TASK_EVIDENCE"),
            AssetRoot("games-unreal-screenshots", games_project / "Saved" / "Screenshots", "UNREAL_CAPTURE"),
            AssetRoot("games-generated", Path("/root/biella/artifacts/games"), "GENERATED_DRAFT"),
            AssetRoot("games-visual-output", games_project / "visual_production" / "outputs", "GENERATED_DRAFT"),
            AssetRoot("games-content", games_project / "Content", "CURRENT_SOURCE"),
        ],
    })
    live = LiveProjection(repo=repo, runtime_root=production_runtime_root, assets=asset_catalog)
    minitz_live = MiniTZLiveProjection(repo=repo, runtime_root=production_runtime_root, assets=asset_catalog, analysis_root=Path("/root/biella/analysis/live_audit"))

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
    print(f"Biella control gateway listening on http://{host}:{port}", flush=True)
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
