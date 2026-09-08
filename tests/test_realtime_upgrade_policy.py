from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/project-state/00_BIELLA_PROJECT_OPERATING_CONTRACT.md"
INSTRUCTIONS = ROOT / "docs/project-state/BIELLA_PROJECT_INSTRUCTIONS.md"
PRODUCTION = ROOT / "docs/project-state/07_BIELLA_PRODUCTION_SYSTEM.md"
STORAGE = ROOT / "docs/project-state/BIELLA_STORAGE_POLICY.md"
AGENTS = ROOT / "ops/workstation/AGENTS.md"


def test_current_policy_is_realtime_upgrade_not_archive_first():
    texts = [p.read_text(encoding="utf-8") for p in (CONTRACT, INSTRUCTIONS, PRODUCTION, STORAGE, AGENTS)]
    for text in texts:
        assert "REALTIME_CANONICAL_UPGRADE" in text
        assert "no parallel archive workflow" in text.lower()
    storage = STORAGE.read_text(encoding="utf-8")
    assert "Biella/ARCHIVE" not in storage
    assert "/root/biella/archive" not in storage
    assert "COLD_STORAGE_INDEX" not in storage


def test_realtime_upgrade_preserves_proof_without_preserving_duplicate_active_state():
    contract = CONTRACT.read_text(encoding="utf-8")
    instructions = INSTRUCTIONS.read_text(encoding="utf-8")
    for text in (contract, instructions):
        assert "Git history" in text
        assert "raw evidence" in text
        assert "replace" in text.lower()
        assert "duplicate active" in text.lower()


def test_website_live_facts_are_deterministic_projection_not_permanent_agent():
    production = PRODUCTION.read_text(encoding="utf-8")
    website_agents = (ROOT / "website/AGENTS.md").read_text(encoding="utf-8")
    for text in (production, website_agents):
        assert "NO_PERMANENT_WEBSITE_AGENT" in text
        assert "/live-api/snapshot" in text
        assert "/live-api/events" in text


def test_03_04_are_current_task_projections_without_superseded_control_files():
    import re
    state_text = (ROOT / "docs/project-state/03_BIELLA_CURRENT_STATE.md").read_text(encoding="utf-8")
    task_text = (ROOT / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").read_text(encoding="utf-8")
    production = (ROOT / "projects/biella-games/docs/PRODUCTION.md").read_text(encoding="utf-8")
    current = re.search(r"^Current task: `([^`]+)`$", production, re.MULTILINE)
    assert current
    task_id = current.group(1)
    assert f"  id: {task_id}" in state_text
    assert f"  id: {task_id}" in task_text
    assert "D03-01\n  project:" not in state_text if task_id != "D03-01" else True
    for stale in (
        "RESUME_OWNER_REQUESTED", "owner-sleep-order.json",
        "owner-resume-order.json", "session_derivative_recovery_backup",
    ):
        assert stale not in state_text
        assert stale not in task_text


def test_production_contract_requires_nonblocking_autoadvance_quality_and_token_efficiency():
    text = (ROOT / "docs/project-state/07_BIELLA_PRODUCTION_SYSTEM.md").read_text(encoding="utf-8")
    for token in (
        "OWNER_ACCEPTANCE_FAST_PATH", "TASK_CLASS_IS_NOT_A_BLOCKER",
        "NO_MONITOR_ONLY_STALL", "NO_EXTERNAL_PROGRESS_HOOK_DEPENDENCY",
        "CACHE_EFFICIENCY_QUALITY_FIRST", "PROJECT_DATA_LEAKAGE_FORBIDDEN",
    ):
        assert token in text


def test_manual_progress_edits_use_sleep_sync_resume_transaction():
    for path in (CONTRACT, INSTRUCTIONS, PRODUCTION):
        text = path.read_text(encoding="utf-8")
        assert "MAINTENANCE_PROGRESS_TRANSACTION" in text
        assert "sleep" in text.lower()
        assert "sync" in text.lower()
        assert "resume" in text.lower()


def test_production_policy_contains_no_no_progress_wait_or_retry_blocker():
    text = PRODUCTION.read_text(encoding="utf-8")
    for forbidden in (
        "marked no-progress and is not called again",
        "production waits without another model call",
        "Packet/no-progress bookkeeping",
    ):
        assert forbidden not in text
