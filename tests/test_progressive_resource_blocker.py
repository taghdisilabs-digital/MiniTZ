from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/local-ai"))
import biella_production_runner as runner


def production_order():
    rows = []
    for line in (ROOT / "projects/biella-games/docs/PRODUCTION.md").read_text().splitlines():
        if line.startswith("- ["):
            rows.append(line.split("|", 1)[0].split()[-1])
    return rows


def task_map():
    data = json.loads((ROOT / "docs/task-program/D_NEXT_100_TASKS.json").read_text())
    return {item["task_id"]: item for item in data["tasks"]}


def test_parked_task_session_can_be_resumed_after_other_task_runs():
    telemetry = runner.initial_runtime()
    telemetry.update({
        "task_session_id": "session-d17",
        "session_task_id": "D17-01",
        "task_sessions": {"D08-01": "session-d08", "D17-01": "session-d17"},
    })
    assert runner._resume_session_for(telemetry, "D08-01") == "session-d08"


def test_win64_blocker_does_not_gate_independent_visual_work():
    order = production_order(); pos = {task_id: index for index, task_id in enumerate(order)}
    assert pos["D17-01"] < pos["D17-08"] < pos["D19-01"] < pos["D20-01"] < pos["D23-01"] < pos["D18-01"] < pos["D18-02"] < pos["D08-01"] < pos["D15-01"]
    rows = task_map()
    assert rows["D17-01"]["depends_on"] == ["D07-01"]
    assert set(rows["D15-01"]["depends_on"]) == {"D17-08", "D08-01"}


def test_resource_blocker_deferral_finds_contiguous_runnable_work():
    import biella_production_state as state
    tasks = [
        state.TaskRecord("DONE", "hard", "done", "COMPLETE", (), "work"),
        state.TaskRecord("BLOCK", "hard", "blocked", "PENDING", (), "work"),
        state.TaskRecord("VIS1", "hard_creation", "visual one", "PENDING", (), "work"),
        state.TaskRecord("VIS2", "hard_creation", "visual two", "PENDING", (), "work"),
        state.TaskRecord("BIND", "hard", "bind", "PENDING", (), "work"),
    ]
    production = state.ProductionState(Path("/tmp/game"), "IN_PROGRESS", "work", "BLOCK", [state.SectionRecord("work", "Work", "IN_PROGRESS", tasks)])
    dependencies = {"BLOCK": ["DONE"], "VIS1": ["DONE"], "VIS2": ["VIS1"], "BIND": ["VIS2", "BLOCK"]}
    assert runner._resource_blocker_deferral_tail(production, "BLOCK", dependencies) == "VIS2"


def test_execution_map_order_tracks_canonical_production_after_deferral(tmp_path):
    import biella_execution_map as execution_map
    import biella_production_state as state
    map_dir = tmp_path / "docs/task-program"; map_dir.mkdir(parents=True)
    (map_dir / "D_NEXT_100_TASKS.json").write_text(json.dumps({
        "registry_is_queue": False,
        "tasks": [
            {"task_id": "BLOCK", "ordinal": 1, "production_ordinal": 1, "title": "blocked", "lane": "Games", "execution_root": "projects/game", "depends_on": []},
            {"task_id": "VIS", "ordinal": 2, "production_ordinal": 2, "title": "visual", "lane": "Games", "execution_root": "projects/game", "depends_on": []},
        ],
    }))
    production = state.ProductionState(tmp_path / "projects/game", "IN_PROGRESS", "work", "VIS", [
        state.SectionRecord("work", "Work", "IN_PROGRESS", [
            state.TaskRecord("VIS", "hard_creation", "visual", "PENDING", (), "work"),
            state.TaskRecord("BLOCK", "hard", "blocked", "PENDING", (), "work"),
        ])
    ])
    synced = execution_map.sync_production_order(tmp_path, production)
    assert [item["task_id"] for item in synced["tasks"]] == ["VIS", "BLOCK"]
    assert [item["ordinal"] for item in synced["tasks"]] == [1, 2]
    assert [item["production_ordinal"] for item in synced["tasks"]] == [1, 2]
