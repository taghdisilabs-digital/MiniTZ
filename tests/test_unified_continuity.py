from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "docs/project-state/03_BIELLA_CURRENT_STATE.md"
TASK = ROOT / "docs/project-state/04_BIELLA_ACTIVE_TASK.md"
PRODUCTION = ROOT / "projects/biella-games/docs/PRODUCTION.md"


def test_current_state_has_one_repo_and_preserves_deferred_engine_frontier():
    text = STATE.read_text(encoding="utf-8")
    assert "repository: patrickminitz-web/biella-engine" in text
    assert "canonical_checkout: /root/biella/repos/biella-engine" in text
    assert "P4-06" in text and "INCOMPLETE_DEFERRED" in text
    assert "FOUNDATION_COMPLETE: false" in text
    assert "/root/biella/repos/biella-games" not in text


def test_consolidation_is_closed_and_games_frontier_is_current():
    state = STATE.read_text(encoding="utf-8")
    task = TASK.read_text(encoding="utf-8")
    production = PRODUCTION.read_text(encoding="utf-8")
    assert "consolidation_state: COMPLETE_VERIFIED" in state
    assert "id: D01-031" in state
    assert "id: D01-031" in task
    assert "BIELLA-CONSOLIDATION-2026-09-05" not in task
    assert "completed_demo_tasks: 30" in state
    assert "queued_successor: D01-031" in state
    assert "runner: READY" in state
    assert "feeder:" not in state
    assert "navigation_state: VERIFIED" in state
    assert "Current task: `D01-031`" in production
    assert production.count("- [x] D01-") == 30
    assert "latest_preservation_commit: f7e74205988cb48946e62efeffe5c5330ec6437b" in state


def test_active_task_is_compact_task_packet_not_historical_ledger():
    text = TASK.read_text(encoding="utf-8")
    for field in ("id:", "project:", "section:", "class:", "title:", "status:", "runner:", "authority:", "continuity:", "preserve:", "stop:"):
        assert field in text
    assert "feeder:" not in text
    assert len(text.splitlines()) < 100


def test_active_games_policy_and_control_runtime_point_only_at_monorepo():
    game_policy = (ROOT / "projects/biella-games/AGENTS.md").read_text(encoding="utf-8")
    runtime = (ROOT / "website/content/control-runtime.json").read_text(encoding="utf-8")
    assert "patrickminitz-web/biella-games" not in game_policy
    assert "/root/biella/repos/biella-games" not in game_policy
    assert "patrickminitz-web/biella-games:main" not in runtime
    assert "patrickminitz-web/biella-engine:main" in runtime
    assert "projects/biella-games" in runtime
