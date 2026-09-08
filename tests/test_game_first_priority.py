from pathlib import Path
from dataclasses import replace
import copy
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/local-ai"))
import biella_production_state as state
import biella_task_ledger as ledger
import biella_task_packet as packets


def production():
    return state.load_project_production(ROOT / "projects/biella-games")


def ids(p):
    return [t.id for s in p.sections for t in s.tasks]


def test_game_first_is_native_production_policy():
    p = production()
    assert p.priority_policy == "GAME_FIRST"
    text = packets.compile_section_packet(p, p.sections[-1], audit=True)
    assert "GAME_FIRST" in text


def test_game_quality_content_and_delivery_precede_unrelated_website():
    order = ids(production()); pos = {key: i for i, key in enumerate(order)}
    assert pos["D08-01"] < pos["D15-01"] < pos["D16-01"]
    assert pos["D17-08"] < pos["D19-01"] < pos["D20-01"]
    assert pos["D20-08"] < pos["D18-03"]
    assert pos["D23-04"] < pos["D09-06"] < pos["D21-01"]


def test_no_invented_cross_product_prerequisite_for_game():
    rows = ledger._registry_rows(ROOT)
    assert rows["D15-01"]["depends_on"] == ["D08-01"]
    assert rows["D19-01"]["depends_on"] == ["D17-08"]
    assert rows["D23-01"]["depends_on"] == ["D20-08"]
    assert "D22-08" in rows["D23-05"]["depends_on"]


def test_all_retained_dependencies_are_earlier_or_completed():
    p = production(); order = ids(p); pos = {x:i for i,x in enumerate(order)}
    done = {t.id for s in p.sections for t in s.tasks if t.status in state._COMPLETE}
    rows = ledger._registry_rows(ROOT)
    for key in order:
        if key in done: continue
        for dep in rows[key]["depends_on"]:
            assert dep in done or (dep in pos and pos[dep] < pos[key]), (key,dep)


def test_ledger_and_horizon_use_production_order_without_new_queue():
    p = production(); built = ledger.build_task_ledger(ROOT,p)
    assert built["priority_policy"] == "GAME_FIRST"
    assert built["execution_order"] == ids(p)
    assert built["registry_is_queue"] is False
    rows = {t["task_id"]:t for t in built["tasks"]}
    for n,key in enumerate(ids(p),1): assert rows[key]["execution_ordinal"] == n
    m=json.loads((ROOT/"docs/task-program/D_NEXT_100_TASKS.json").read_text())
    assert len(m["tasks"]) == len({t["task_id"] for t in m["tasks"]}) == 100
    pos={key:i for i,key in enumerate(ids(p))}
    assert [t["task_id"] for t in m["tasks"]] == sorted((t["task_id"] for t in m["tasks"]),key=pos.get)


def test_native_autofeeder_follows_reordered_rows_without_replaying_completed():
    p=copy.deepcopy(production()); before=state.completed_count(p)
    expected=[t.id for s in p.sections for t in s.tasks if t.status not in state._COMPLETE]
    seen=[]
    for key in expected:
        assert state.next_task(p).id == key
        seen.append(key)
        for s in p.sections:
            s.tasks=[replace(t,status="COMPLETE") if t.id==key else t for t in s.tasks]
    assert state.next_task(p) is None
    assert len(seen)+before == len(ids(p))


def test_priority_survives_active_record_and_ledger_regeneration(tmp_path):
    project=tmp_path/"projects/biella-games"; (project/"docs").mkdir(parents=True)
    (tmp_path/"docs/project-state").mkdir(parents=True)
    (project/"docs/PRODUCTION.md").write_text("# Production\nStatus: `IN_PROGRESS`\nPriority: `GAME_FIRST`\nCurrent section: `post_d01`\nCurrent task: `D08-01`\n## Section: post_d01 | Work | PENDING\n- [ ] D08-01 | hard | Delivery | PENDING | \n- [ ] D15-01 | hard | Bind game | PENDING | \n- [ ] D09-06 | hard | Website | PENDING | \n")
    p=state.load_project_production(project)
    state.write_active_task(tmp_path,state.next_task(p))
    assert "priority: GAME_FIRST" in state.active_task_path(tmp_path).read_text()
    state.mark_task_complete(tmp_path,project,"D08-01","COMPLETE",["fixture proof"])
    assert state.load_active_task(tmp_path).id == "D15-01"
    assert "priority: GAME_FIRST" in state.active_task_path(tmp_path).read_text()
    assert ledger.build_task_ledger(tmp_path,state.load_project_production(project))["priority_policy"]=="GAME_FIRST"


def test_existing_session_resume_receives_current_owner_priority(tmp_path):
    import biella_production_runner as runner
    p=production(); task=state.next_task(p)
    telemetry={"session_task_id":task.id,"task_session_id":"existing-session"}
    prompt=runner._task_prompt(ROOT,p,task,telemetry,tmp_path/"capsule.json")
    assert "PRODUCTION_PRIORITY: GAME_FIRST" in prompt
    assert "RESUME_EXISTING_TASK_SESSION" in prompt
