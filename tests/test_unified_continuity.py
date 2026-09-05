import re
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
    current_match = re.search(r"^Current task: `([^`]+)`$", production, re.MULTILINE)
    progress_match = re.search(r"^Progress: `(\d+)/50` Demo tasks complete$", production, re.MULTILINE)
    assert current_match and progress_match
    current_task = current_match.group(1)
    completed = int(progress_match.group(1))
    assert "consolidation_state: COMPLETE_VERIFIED" in state
    assert f"id: {current_task}" in state
    assert f"id: {current_task}" in task
    assert "BIELLA-CONSOLIDATION-2026-09-05" not in task
    assert f"completed_demo_tasks: {completed}" in state
    assert f"queued_successor: {current_task}" in state
    assert "runner: READY" in state
    assert "feeder:" not in state
    assert "execution_started:" not in state
    assert "execution_started:" not in task
    assert "navigation_state: VERIFIED" in state
    assert production.count("- [x] D01-") == completed
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
