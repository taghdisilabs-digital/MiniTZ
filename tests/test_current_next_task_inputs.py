from pathlib import Path
import os, re, json, hashlib
ROOT = Path(os.environ.get("MINITZ_TEST_REPO", Path(__file__).resolve().parents[1]))
G = ROOT / "projects/minitz-games"


def test_current_and_next_guides_bind_contract_sections_to_real_paths():
    needed = {"D07-01": {"AAA_TPP_RUNTIME_CONTRACTS_11_20.md": [17,18], "AAA_TPP_RUNTIME_CONTRACTS_40_49.md": list(range(40,50))}, "D08-01": {"AAA_TPP_RUNTIME_CONTRACTS_21_23.md": [23], "AAA_TPP_RUNTIME_CONTRACTS_50_59.md": [55,58,59]}}
    for task, groups in needed.items():
        guide = (G / "docs/task-guides" / (task + ".md")).read_text()
        for filename, sections in groups.items():
            relative = "docs/runtime-contracts/" + filename
            assert relative in guide, (task, relative)
            text = (G / relative).read_text()
            for section in sections:
                assert re.search(r"^## " + str(section) + r" [—–-]", text, re.M)


def test_d08_handoff_records_real_resource_limits_without_changing_acceptance():
    guide = (G / "docs/task-guides/D08-01.md").read_text()
    assert "D08-01-resource-observation.json" in guide
    receipt = json.loads((G / "Build/Release/D08-01/D08-01-resource-observation.json").read_text())
    assert receipt["task_id"] == "D08-01"
    assert receipt["acceptance_changed"] is False
    assert receipt["observation_only"] is True
    assert receipt["compatible_win64_runtime_verified"] is False
    assert receipt["windows_node"]["registry_build_tools"]
    assert receipt["windows_node"]["registry_sdk"]
    assert "no repeated installation" in guide.lower()


def test_affected_map_guide_digests_match_current_source():
    entries = json.loads((ROOT / "docs/task-program/D_NEXT_100_TASKS.json").read_text())["tasks"]
    for task in ("D07-01", "D08-01"):
        entry = next(x for x in entries if x["task_id"] == task)
        relative = "projects/minitz-games/docs/task-guides/" + task + ".md"
        ref = next(x for x in entry["source_refs"] if x["path"] == relative)
        assert ref["sha256"] == hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
