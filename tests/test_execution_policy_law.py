from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICIES = [
    ROOT / "docs/project-state/00_BIELLA_PROJECT_OPERATING_CONTRACT.md",
    ROOT / "docs/project-state/BIELLA_PROJECT_INSTRUCTIONS.md",
    ROOT / "docs/project-state/BIELLA_DURABLE_SOURCE_AND_SYNC_RULES.md",
    ROOT / "ops/workstation/AGENTS.md",
    ROOT / "projects/biella-games/AGENTS.md",
    ROOT / "website/AGENTS.md",
    ROOT / "website/docs/CONTROL_CONSOLE_GATEWAY_CONTRACT.md",
]
MARKERS = (
    "SINGLE_CODEX_AUTHORITY",
    "RESOURCE_PARALLELISM",
    "LOCAL_FIRST_EFFICIENCY",
    "FINAL_DELIVERABLE_PUBLICATION",
    "DURABLE_FAILURE_LEDGER",
    "LOSSLESS_MEMORY_COMPACTION",
    "VERIFIED_ACTION_MEMORY",
)


def test_current_execution_policies_share_hardened_execution_law():
    for path in POLICIES:
        text = path.read_text(encoding="utf-8")
        for marker in MARKERS:
            assert marker in text, f"{path}: missing {marker}"
        assert "failures.jsonl" in text, path
        assert "never invent a destination" in text.lower(), path
        assert "must never stall" in text.lower(), path
        assert "content-addressed unique records" in text.lower(), path
