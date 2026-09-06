from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "projects/biella-games/docs/task-guides"
EXPECTED = {
    "D03-01": (3, (4, 14, 16, 20, 21, 37, 39, 46, 49)),
    "D04-01": (4, (25, 29, 32, 52, 53, 55)),
    "D05-01": (5, (24, 38, 51, 56, 57)),
    "D06-01": (6, (36,)),
    "D07-01": (7, (17, 18, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49)),
    "D08-01": (8, (23, 55, 58, 59)),
}


def test_current_and_next_five_task_guides_are_complete_and_ordered():
    production = (ROOT / "projects/biella-games/docs/PRODUCTION.md").read_text()
    sequence = (ROOT / "projects/biella-games/docs/IMPLEMENTATION_SEQUENCE.md").read_text()
    for task_id, (stage, contracts) in EXPECTED.items():
        path = GUIDES / f"{task_id}.md"
        assert path.exists(), task_id
        text = path.read_text()
        assert f"task_id: {task_id}" in text
        assert f"stage: {stage}" in text
        assert "## Objective" in text
        assert "## Execution law" in text
        assert "TODO" not in text and "TBD" not in text
        assert task_id in production
        assert f"Stage {stage}" in sequence
        for contract in contracts:
            assert f"{contract:02d}" in text


def test_guides_remove_known_nonfunctional_stall_patterns():
    combined = "\n".join((GUIDES / f"{task_id}.md").read_text() for task_id in EXPECTED)
    assert "Do not pause for naming approval" in combined
    assert "Local Qwen is optional on-demand assistance" in combined
    assert "`03/04` are volatile continuity state and are not gameplay byte-identity gates" in combined
    assert "do not invent" in combined.lower()
