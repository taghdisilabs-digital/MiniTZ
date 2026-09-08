#!/usr/bin/env python3
# Verify D17-01 closes selection only and preserves downstream quality gates.
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
ROOT = PROJECT / "Build/AAA/D17-01"

def read(path):
    return json.loads(Path(path).read_text())

def main():
    registry = read(REPO / "docs/task-program/D_NEXT_100_TASKS.json")
    tasks = {row["task_id"]: row for row in registry["tasks"]}
    task = tasks["D17-01"]
    assert task["title"] == "Select canonical AAA challenger slice"
    assert task["depends_on"] == ["D07-01"]
    assert task["required_evidence"] == "Scenario file, package identity, first raw run capture."
    assert tasks["D17-02"]["depends_on"] == ["D17-01"]
    assert tasks["D17-04"]["depends_on"] == ["D17-03"]
    assert tasks["D17-07"]["depends_on"] == ["D17-06"]
    assert tasks["D17-08"]["depends_on"] == ["D17-07"]
    q = read(ROOT / "qualification.json")
    scenario = read(ROOT / "scenario.json")
    visual = read(ROOT / "visual-assessment.json")
    assert q["task_id"] == "D17-01"
    assert q["status"] == "COMPLETE" and q["result"] == "PASS" and q["accepted"]
    assert q["evidence_integrity"] == "VERIFIED" and q["unmet_criteria"] == []
    assert {g["id"] for g in q["downstream_gaps"]} == {"continuous_slice_duration_and_route", "player_rival_infected_arena_pressure", "final_layer_quality"}
    assert scenario["duration_contract_seconds"] == [600, 1200]
    assert scenario["task_selection_status"] == "D17-01_COMPLETE"
    assert len(scenario["route"]) >= 7
    assert scenario["current_package"]["package_id"] == q["package"]["package_id"]
    assert q["first_raw_run"]["raw_video"]["bytes"] > 0
    assert q["first_raw_run"]["input_actions"] > 0
    assert visual["major_defects"] and not visual["zero_major_defects"]
    print(json.dumps({"task_id":"D17-01","result":"PASS","selection_complete":True,"final_slice_complete":False,"downstream_gap_count":len(q["downstream_gaps"])}, sort_keys=True))

if __name__ == "__main__":
    main()
