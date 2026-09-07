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
