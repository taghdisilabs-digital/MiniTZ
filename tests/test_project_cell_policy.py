from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "docs/project-state/BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml"
SOURCE_MAP = ROOT / "docs/project-state/06_BIELLA_SOURCE_EVIDENCE_MAP.yaml"
INSTRUCTIONS = ROOT / "docs/project-state/BIELLA_PROJECT_INSTRUCTIONS.md"
PRODUCTION = ROOT / "docs/project-state/07_BIELLA_PRODUCTION_SYSTEM.md"
DRIVE = ROOT / "docs/project-state/BIELLA_DRIVE_LIVE_MANIFEST.md"
AGENTS = ROOT / "ops/workstation/AGENTS.md"

BRIDGE_SHA = "b92b77ee6a4a7791217b0346225f8a893c1b7dad27c8f5c56d467621aac9d7be"
DRIVE_ID = "1x35z0cZ-t3SM3Ma6mX5O4AMfFKnDcolv"


def test_approved_bridge_is_registered_as_current_machine_guidance():
    assert BRIDGE.is_file()
    text = SOURCE_MAP.read_text(encoding="utf-8")
    assert "isolated_project_execution_bridge:" in text
    assert "BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml" in text
    assert BRIDGE_SHA in text
    assert DRIVE_ID in text
    assert "CURRENT_GITHUB_SOURCE" in text


def test_current_execution_policies_define_biella_owned_project_cells():
    instructions = INSTRUCTIONS.read_text(encoding="utf-8")
    production = PRODUCTION.read_text(encoding="utf-8")
    agents = AGENTS.read_text(encoding="utf-8")
    for text in (instructions, production, agents):
        assert "ISOLATED_PROJECT_CELL" in text
        assert "chatgpt_remote" in text
        assert "replaceable" in text.lower()
    assert "Biella owns task execution" in instructions
    assert "project-specific state remains inside the Project cell" in instructions


def test_drive_manifest_points_to_exact_bridge_object_and_git_counterpart():
    text = DRIVE.read_text(encoding="utf-8")
    assert "BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml" in text
    assert DRIVE_ID in text
    assert "docs/project-state/BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml" in text
    assert BRIDGE_SHA in text
