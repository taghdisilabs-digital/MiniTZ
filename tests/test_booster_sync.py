from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/minitz_booster_sync.py"
sys.path.insert(0, str(ROOT / "ops/local-ai"))


def load_module():
    assert MODULE.is_file(), "persistent Booster synchronizer is not implemented"
    spec = importlib.util.spec_from_file_location("minitz_booster_sync", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_booster_channels_match_canonical_boost_fabric_partition():
    sync = load_module()
    import minitz_boost_fabric as fabric
    expected = {group.boost_id: group.commander_lanes for group in fabric.boost_groups()}
    actual = {
        boost_id: tuple(lane_id for lane_id, _role in channels)
        for boost_id, channels in sync.BOOSTER_CHANNELS.items()
    }
    assert actual == expected


def test_current_task_row_uses_live_boost_fabric_when_legacy_current_execution_is_absent():
    mod = load_module()
    live = program()
    live.pop("current_execution")
    live["frozen_current_task"] = {"task_id": "T2", "session_id": None}
    live["tasks"][1]["status"] = "WORKING"
    row = mod._current_task_row(live)
    assert row["task_id"] == "T2"
    assert row["revision"] == 3


def test_current_task_row_ignores_stale_legacy_current_execution():
    mod = load_module()
    live = program()
    live["current_execution"] = {"task_id": "T9", "task_revision": 99, "task_sha256": "z" * 64}
    live["tasks"][1]["status"] = "WORKING"
    row = mod._current_task_row(live)
    assert row["task_id"] == "T2"
    assert row["revision"] == 3
    assert row["task_record_sha256"] == "b" * 64


def program():
    return {
        "program_id": "P",
        "revision": 7,
        "current_execution": {"task_id": "T2", "task_revision": 3, "task_sha256": "b" * 64},
        "tasks": [
            {"task_id": "T1", "revision": 2, "task_record_sha256": "a" * 64, "status": "COMPLETE", "title": "done", "dependencies": []},
            {"task_id": "T2", "revision": 3, "task_record_sha256": "b" * 64, "status": "PENDING", "title": "current evidence task", "dependencies": [{"dependency_type": "HARD", "task_ref": "T1"}], "objective": {"desired_state": "unify evidence"}, "acceptance": ["exact evidence"], "inputs": [{"kind": "CURRENT_SOURCE", "path": "src/a.py"}], "required_capabilities": ["evidence.record"], "write_scope": {"authority": "TASK_OWNED_ONLY", "allowed_paths": ["src/a.py"], "execution_root": "/workspace/repo"}},
            {"task_id": "T3", "revision": 1, "task_record_sha256": "c" * 64, "status": "PENDING", "title": "blocked task", "dependencies": [{"dependency_type": "HARD", "task_ref": "T9"}]},
            {"task_id": "T9", "revision": 1, "task_record_sha256": "d" * 64, "status": "PENDING", "title": "dependency", "dependencies": []},
        ],
    }


def ledger():
    return {
        "schema": "minitz.booster_work_program/v1",
        "canonical_program_revision": 5,
        "canonical_program_sha256": "old",
        "allowed_work_status": ["QUEUED", "IN_PROGRESS", "DONE_LOCAL", "BLOCKED_CANONICAL_DEPENDENCY", "BLOCKED_TECHNICAL", "HANDOFF_READY", "SUPERSEDED"],
        "items": [
            {"booster": "BOOST-02", "canonical_task_id": "T1", "canonical_task_revision": 1, "canonical_task_sha256": "old1", "queue_order": 1, "work_status": "QUEUED", "cycle_count": 0, "evidence_refs": [], "files_changed": []},
            {"booster": "BOOST-02", "canonical_task_id": "T2", "canonical_task_revision": 2, "canonical_task_sha256": "old2", "queue_order": 2, "work_status": "BLOCKED_CANONICAL_DEPENDENCY", "cycle_count": 1, "evidence_refs": ["evidence://old"], "files_changed": []},
            {"booster": "BOOST-02", "canonical_task_id": "T3", "canonical_task_revision": 1, "canonical_task_sha256": "c" * 64, "queue_order": 3, "work_status": "QUEUED", "cycle_count": 0, "evidence_refs": [], "files_changed": []},
            {"booster": "BOOST-03", "canonical_task_id": "T2", "canonical_task_revision": 3, "canonical_task_sha256": "b" * 64, "queue_order": 1, "work_status": "HANDOFF_READY", "cycle_count": 1, "handoff_to": "BOOST-02", "summary": "publication evidence ready", "evidence_refs": ["evidence://handoff"], "files_changed": ["src/pub.py"]},
        ],
    }


def test_reconcile_ledger_updates_live_task_identity_dependencies_and_skips_complete():
    mod = load_module()
    reconciled = mod.reconcile_ledger(program(), ledger(), program_sha256="live-sha")
    assert reconciled["canonical_program_revision"] == 7
    assert reconciled["canonical_program_sha256"] == "live-sha"
    assert "NEEDS_REBASE" in reconciled["allowed_work_status"]
    rows = {row["canonical_task_id"]: row for row in reconciled["items"] if row["booster"] == "BOOST-02"}
    assert rows["T1"]["work_status"] == "SUPERSEDED"
    assert rows["T1"]["canonical_status"] == "COMPLETE"
    assert rows["T2"]["canonical_task_revision"] == 3
    assert rows["T2"]["canonical_task_sha256"] == "b" * 64
    assert rows["T2"]["work_status"] == "NEEDS_REBASE"
    assert rows["T2"]["unmet_hard_dependencies"] == []
    assert rows["T3"]["work_status"] == "BLOCKED_CANONICAL_DEPENDENCY"
    assert rows["T3"]["unmet_hard_dependencies"] == ["T9"]
    assert rows["T2"]["evidence_refs"] == ["evidence://old"]
    assert rows["T2"]["task_description"] == "unify evidence"
    assert rows["T2"]["primary_files_or_scopes"] == ["src/a.py"]


def test_select_next_work_prefers_rebase_or_in_progress_and_never_redoes_done():
    mod = load_module()
    current = mod.reconcile_ledger(program(), ledger(), program_sha256="live-sha")
    selected = mod.select_next_work(current, "BOOST-02")
    assert selected["canonical_task_id"] == "T2"
    selected["work_status"] = "DONE_LOCAL"
    selected = mod.select_next_work(current, "BOOST-02")
    assert selected is None


def test_build_context_pack_is_bounded_has_six_channels_handoff_memory_and_reserved_services(tmp_path):
    mod = load_module()
    current = mod.reconcile_ledger(program(), ledger(), program_sha256="live-sha")
    mem = {
        "schema": "biella.compacted_memory/v1",
        "records": [
            {"category": "task_memory", "task_id": "T2", "task_revision": 3, "task_sha256": "b" * 64, "content_ref": "sha256:m1", "source_ref": "task-memory/T2.json"},
            {"category": "failure", "task_id": "T2", "task_revision": 3, "task_sha256": "b" * 64, "content_ref": "sha256:m2", "source_ref": "failures.jsonl:2"},
            {"category": "instruction", "content_ref": "sha256:m3", "source_ref": "AGENTS.md:1", "scope_ref": "scope://minitz/system"},
        ],
        "content": {
            "sha256:m1": {"text": "T2 preserve evidence and reuse prior work"},
            "sha256:m2": {"text": "T2 exact failed validation"},
            "sha256:m3": {"text": "MiniTZ OS authority remains singular"},
        },
    }
    projection = {"schema": "biella.compacted_task_projection/v1", "task_id": "T2", "source_refs": ["src/a.py"], "failures": [{"text": "current failure"}]}
    registry = {
        "policy": {"resource_loop": {"state": "RESERVED_NOT_STARTED", "automatic_dispatch": False}},
        "routes": {"llm.code": ["ollama-qwen", "groq"], "observability.query": ["axiom"], "research.search": ["tavily", "exa"]},
        "providers": {"ollama-qwen": {"cost_class": "local_compute"}, "groq": {"cost_class": "credit_or_paid"}, "axiom": {"cost_class": "credit_or_paid"}, "tavily": {"cost_class": "credit_or_paid"}, "exa": {"cost_class": "credit_or_paid"}},
    }
    pack = mod.build_context_pack(program(), current, "BOOST-02", memory_index=mem, projection=projection, provider_registry=registry, maximum_bytes=18000)
    assert pack["booster_id"] == "BOOST-02"
    assert pack["selected_task"]["task_id"] == "T2"
    assert len(pack["channels"]) == 6
    assert len({row["lane_id"] for row in pack["channels"]}) == 6
    assert pack["incoming_handoffs"][0]["from_booster"] == "BOOST-03"
    assert any("prior work" in str(row) for row in pack["memory"]["records"])
    assert pack["services"]["dispatch_allowed"] is False
    assert pack["services"]["external_loop_state"] == "RESERVED_NOT_STARTED"
    assert pack["services"]["primary_local"] == "ollama-qwen"
    assert len(json.dumps(pack).encode()) <= 18000


def test_local_ai_assist_is_content_addressed_and_reused(tmp_path):
    mod = load_module()
    pack = {"project_scope": "minitz", "booster_id": "BOOST-01", "selected_task": {"task_id": "T"}, "context": "bounded"}
    calls = []
    def invoke(prompt):
        calls.append(prompt)
        return {"provider": "ollama-qwen", "model": "qwen", "text": "useful", "usage": {"total_tokens": 5}}
    first = mod.ensure_local_ai_assist(pack, tmp_path, invoke)
    second = mod.ensure_local_ai_assist(pack, tmp_path, invoke)
    assert first == second
    assert len(calls) == 1
    data = json.loads(first.read_text())
    assert data["provider"] == "ollama-qwen"
    assert data["authority"] == "NONE"


def test_local_ai_assist_rejects_unscoped_cache(tmp_path):
    mod = load_module()
    pack = {"booster_id": "BOOST-01", "selected_task": {"task_id": "T"}, "context": "bounded"}
    try:
        mod.ensure_local_ai_assist(pack, tmp_path, lambda _prompt: {"provider": "ollama-qwen", "text": "x"})
    except ValueError as exc:
        assert "Project scope" in str(exc)
    else:
        raise AssertionError("unscoped Booster cache must be rejected")


def test_main_coder_handoff_only_exposes_finished_current_task_booster_work():
    mod = load_module()
    current = mod.reconcile_ledger(program(), ledger(), program_sha256="live-sha")
    for row in current["items"]:
        if row["booster"] == "BOOST-02" and row["canonical_task_id"] == "T2":
            row.update({"work_status": "DONE_LOCAL", "summary": "evidence implementation finished", "evidence_refs": ["evidence://done"], "files_changed": ["src/a.py"]})
    payload = mod.build_main_coder_handoff(program(), current)
    assert payload["task_id"] == "T2"
    assert {row["booster"] for row in payload["booster_results"]} == {"BOOST-02", "BOOST-03"}
    assert all(row["work_status"] in {"DONE_LOCAL", "HANDOFF_READY"} for row in payload["booster_results"])


def test_sync_files_writes_five_contexts_and_reconciled_ledger(tmp_path):
    mod = load_module()
    program_path = tmp_path / "TASK_PROGRAM.json"; program_path.write_text(json.dumps(program()))
    ledger_path = tmp_path / "BOOSTER_TASK_LIST.json"; ledger_path.write_text(json.dumps(ledger()))
    memory_path = tmp_path / "memory.json"; memory_path.write_text(json.dumps({"records": [], "content": {}}))
    projection_path = tmp_path / "projection.json"; projection_path.write_text(json.dumps({"task_id": "T2"}))
    registry_path = tmp_path / "registry.json"; registry_path.write_text(json.dumps({"policy": {"resource_loop": {"state": "RESERVED_NOT_STARTED"}}, "routes": {"llm.code": ["ollama-qwen"]}, "providers": {"ollama-qwen": {}}}))
    context_root = tmp_path / "contexts"
    result = mod.sync_files(program_path, ledger_path, memory_path, projection_path, registry_path, context_root=context_root)
    assert result["program_revision"] == 7
    assert set(result["contexts"]) == {f"BOOST-{i:02d}" for i in range(1, 6)}
    assert all(Path(path).is_file() for path in result["contexts"].values())
    saved = json.loads(ledger_path.read_text())
    assert saved["canonical_program_revision"] == 7
    assert (context_root / "main-coder-context.json").is_file()


def test_claim_and_report_update_only_owned_entry_atomically(tmp_path):
    mod = load_module()
    current = mod.reconcile_ledger(program(), ledger(), program_sha256="live")
    ledger_path = tmp_path / "ledger.json"; ledger_path.write_text(json.dumps(current))
    claimed = mod.claim_work(ledger_path, "BOOST-02")
    assert claimed["canonical_task_id"] == "T2"
    assert claimed["work_status"] == "IN_PROGRESS"
    assert claimed["cycle_count"] == 2
    other_before = [x for x in current["items"] if x["booster"] == "BOOST-03"][0]
    reported = mod.report_work(ledger_path, "BOOST-02", "T2", status="DONE_LOCAL", summary="finished", files_changed=["src/a.py"], evidence_refs=["evidence://ok"], next_action="main coder validate")
    assert reported["work_status"] == "DONE_LOCAL"
    assert reported["files_changed"] == ["src/a.py"]
    saved = json.loads(ledger_path.read_text())
    other_after = [x for x in saved["items"] if x["booster"] == "BOOST-03"][0]
    assert other_after == other_before


def test_local_qwen_invocation_is_single_provider_no_failover_and_bounded(monkeypatch):
    mod = load_module()
    seen = {}
    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps({"provider": "ollama-qwen", "model": "qwen", "text": "ok", "usage": {}})
    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return Result()
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    result = mod._invoke_local_qwen("x" * 20000, command="/usr/local/bin/biella")
    argv = seen["argv"]
    assert argv[argv.index("--provider") + 1] == "ollama-qwen"
    assert argv[argv.index("--max-failover-attempts") + 1] == "1"
    assert argv[argv.index("--timeout-seconds") + 1] == "80"
    assert len(argv[argv.index("--prompt") + 1]) <= 7000
    assert result["provider"] == "ollama-qwen"


def test_context_digest_is_project_scoped():
    mod = load_module()
    base = {"project_scope": "minitz", "booster_id": "BOOST-02", "selected_task": {"task_id": "T2", "revision": 3}}
    other = json.loads(json.dumps(base))
    other["project_scope"] = "customer-a"
    assert mod.context_digest(base) != mod.context_digest(other)


def test_context_digest_ignores_volatile_cycle_metadata_but_not_evidence_changes():
    mod = load_module()
    base = {"booster_id": "BOOST-02", "selected_task": {"task_id": "T2", "revision": 3}, "ledger_entry": {"canonical_task_id": "T2", "cycle_count": 1, "work_status": "IN_PROGRESS", "last_claimed_at": "a", "summary": "same", "evidence_refs": ["e1"]}}
    second = json.loads(json.dumps(base)); second["ledger_entry"].update({"cycle_count": 2, "last_claimed_at": "b", "work_status": "IN_PROGRESS"})
    assert mod.context_digest(base) == mod.context_digest(second)
    second["ledger_entry"]["evidence_refs"] = ["e1", "e2"]
    assert mod.context_digest(base) != mod.context_digest(second)


def test_synced_context_declares_sandbox_write_boundary(tmp_path):
    mod = load_module()
    program_path = tmp_path / "TASK_PROGRAM.json"; program_path.write_text(json.dumps(program()))
    ledger_path = tmp_path / "BOOSTER_TASK_LIST.json"; ledger_path.write_text(json.dumps(ledger()))
    memory_path = tmp_path / "memory.json"; memory_path.write_text(json.dumps({"records": [], "content": {}}))
    projection_path = tmp_path / "projection.json"; projection_path.write_text(json.dumps({"task_id": "T2"}))
    registry_path = tmp_path / "registry.json"; registry_path.write_text(json.dumps({"policy": {"resource_loop": {"state": "RESERVED_NOT_STARTED"}}, "routes": {"llm.code": ["ollama-qwen"]}, "providers": {"ollama-qwen": {}}}))
    context_root = tmp_path / "contexts"
    mod.sync_files(program_path, ledger_path, memory_path, projection_path, registry_path, context_root=context_root)
    pack = json.loads((context_root / "BOOST-02.json").read_text())
    assert pack["sandbox"]["host_workspace"] == "/root/attached-storage/minitz-os-sandbox/workspace/boosts/BOOST-02"
    assert pack["sandbox"]["container_workspace"] == "/workspace/repo"
    assert pack["sandbox"]["exec_wrapper"].endswith("exec-booster.sh")
    assert pack["sandbox"]["host_os_mutation_allowed"] is False
    assert pack["sandbox"]["normal_network"] == "AVAILABLE"


def test_main_coder_handoff_includes_exact_current_qwen_assists(tmp_path):
    mod = load_module()
    program = {
        "current_execution": {"task_id": "UNIFY-06", "task_revision": 5, "task_sha256": "a" * 64},
    }
    ledger = {"items": []}
    context_root = tmp_path / "context"; context_root.mkdir()
    local_ai_root = tmp_path / "local-ai"
    assists = {}
    for booster in mod.BOOSTER_CHANNELS:
        pack = {"project_scope": "minitz", "booster_id": booster, "selected_task": {"task_id": "UPCOMING-1"}}
        (context_root / f"{booster}.json").write_text(json.dumps(pack))
        digest = mod.context_digest(pack)
        path = local_ai_root / booster / f"UPCOMING-1-{digest[:20]}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "minitz.booster_local_ai_assist/v1", "authority": "NONE",
            "progression_authority": False, "project_scope": "minitz", "booster_id": booster, "task_id": "UPCOMING-1",
            "context_digest": digest, "provider": "ollama-qwen", "model": "qwen",
            "text": f"{booster} bounded upcoming-task guidance", "usage": {}, "created_at": "2026-09-11T00:00:00Z",
        }
        path.write_text(json.dumps(payload))
        assists[booster] = str(path)

    handoff = mod.build_main_coder_handoff(
        program, ledger, local_ai_assists=mod.collect_current_local_ai_assists(context_root, local_ai_root)
    )

    assert len(handoff["local_qwen_assists"]) == 5
    assert {row["booster"] for row in handoff["local_qwen_assists"]} == set(mod.BOOSTER_CHANNELS)
    assert all(row["authority"] == "NONE" and row["progression_authority"] is False for row in handoff["local_qwen_assists"])
    assert all("bounded upcoming-task guidance" in row["text"] for row in handoff["local_qwen_assists"])


def test_collect_current_local_ai_assists_rejects_cross_project_payload(tmp_path):
    mod = load_module()
    context_root = tmp_path / "context"; context_root.mkdir()
    local_ai_root = tmp_path / "local-ai"
    pack = {"project_scope": "minitz", "booster_id": "BOOST-01", "selected_task": {"task_id": "T"}}
    (context_root / "BOOST-01.json").write_text(json.dumps(pack))
    digest = mod.context_digest(pack)
    path = local_ai_root / "BOOST-01" / f"T-{digest[:20]}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "schema": "minitz.booster_local_ai_assist/v1", "authority": "NONE",
        "progression_authority": False, "project_scope": "customer-a",
        "booster_id": "BOOST-01", "task_id": "T", "context_digest": digest,
        "provider": "ollama-qwen", "model": "qwen", "text": "wrong project",
    }))
    assert mod.collect_current_local_ai_assists(context_root, local_ai_root) == []


def test_refresh_context_privacy_receipts_rebinds_exact_current_context(tmp_path):
    mod = load_module()
    context_root = tmp_path / "context"; context_root.mkdir()
    target = context_root / "BOOST-01.json"
    target.write_text(json.dumps({"booster_id":"BOOST-01","selected_task":{"task_id":"T"}}))
    config_source = tmp_path / "runtime.env"
    config_source.write_text("SAFE_CONFIG=enabled\n")

    receipts = mod.refresh_context_privacy_receipts(context_root, config_source)

    receipt_path = Path(receipts["BOOST-01"])
    receipt = json.loads(receipt_path.read_text())
    assert receipt["result"] == "PASS"
    assert receipt["exact_value_hit_count"] == 0
    assert receipt["unknown_entry_count"] == 0
    assert receipt["target_identity_digests"][0]["content_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


def test_prepare_local_ai_for_one_booster_does_not_generate_other_feeds(tmp_path, monkeypatch):
    mod = load_module()
    context_root = tmp_path / "context"; context_root.mkdir()
    for booster in ("BOOST-01", "BOOST-02"):
        (context_root / f"{booster}.json").write_text(json.dumps({"project_scope": "minitz", "booster_id": booster, "selected_task": {"task_id": "T"}, "ledger_entry": {"summary": "x"}}))
    privacy = context_root / "privacy"; privacy.mkdir()
    target = context_root / "BOOST-02.json"
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (privacy / "BOOST-02.json").write_text(json.dumps({
        "schema": "minitz.private_secret_leak_receipt/v3", "result": "PASS",
        "exact_value_hit_count": 0, "unknown_entry_count": 0,
        "target_identity_digests": [{"content_sha256": digest}],
    }))
    calls = []
    monkeypatch.setattr(mod, "_invoke_local_qwen", lambda prompt, **kwargs: calls.append(prompt) or {"provider": "ollama-qwen", "model": "qwen", "text": "ok", "usage": {}})
    path = mod.prepare_local_ai_for_booster(context_root, tmp_path / "ai", "BOOST-02")
    assert path.is_file()
    assert "BOOST-02" in str(path)
    assert len(calls) == 1
    assert not (tmp_path / "ai" / "BOOST-01").exists()



def test_idle_booster_context_falls_back_to_exact_current_task():
    mod = load_module()
    current = mod.reconcile_ledger(program(), ledger(), program_sha256="live-sha")
    pack = mod.build_context_pack(
        program(), current, "BOOST-01",
        memory_index={"records": [], "content": {}},
        projection={"task_id": "T2", "source_refs": ["src/a.py"]},
        provider_registry={"policy": {"resource_loop": {"state": "RESERVED_NOT_STARTED"}}, "routes": {}, "providers": {}},
    )
    assert pack["idle_capacity"] is True
    assert pack["ledger_entry"] is None
    assert pack["selected_task"]["task_id"] == "T2"
    assert pack["selected_task"]["revision"] == 3
    assert pack["selected_task"]["task_record_sha256"] == "b" * 64


def test_qwen_idle_plan_is_bounded_lane_owned_and_content_addressed(tmp_path):
    mod = load_module()
    pack = {
        "booster_id": "BOOST-01", "idle_capacity": True,
        "selected_task": {"task_id": "T2", "revision": 3, "task_record_sha256": "b" * 64, "title": "current evidence task"},
        "canonical_program": {"revision": 7, "sha256": "e" * 64},
        "channels": [{"lane_id": lane, "role": role} for lane, role in mod.BOOSTER_CHANNELS["BOOST-01"]],
    }
    raw = {"provider": "ollama-qwen", "model": "qwen", "usage": {"total_tokens": 9}, "text": json.dumps({
        "summary": "Use idle capacity on current evidence work.",
        "work_units": [{
            "title": "Trace current evidence source", "objective": "Find the exact current source boundary",
                "lane_id": "CMD-01", "evidence_goal": "Exact source and digest", "mode": "READ_ONLY",
        }],
    })}
    calls = []
    first = mod.ensure_idle_qwen_plan(pack, tmp_path, lambda prompt: calls.append(prompt) or raw)
    second = mod.ensure_idle_qwen_plan(pack, tmp_path, lambda prompt: calls.append(prompt) or raw)
    assert first == second
    assert len(calls) == 1
    data = json.loads(first.read_text())
    assert data["schema"] == "minitz.qwen_idle_boost_plan/v1"
    assert data["task_id"] == "T2"
    assert data["progression_authority"] is False
    assert data["work_units"][0]["lane_id"] == "CMD-01"
    assert data["work_units"][0]["mode"] == "READ_ONLY"
    assert data["work_units"][0]["work_unit_id"].startswith("QWEN-")


def test_qwen_idle_plan_rejects_foreign_commander_lane(tmp_path):
    mod = load_module()
    pack = {
        "booster_id": "BOOST-01", "idle_capacity": True,
        "selected_task": {"task_id": "T2", "revision": 3, "task_record_sha256": "b" * 64},
        "canonical_program": {"revision": 7, "sha256": "e" * 64},
        "channels": [{"lane_id": lane, "role": role} for lane, role in mod.BOOSTER_CHANNELS["BOOST-01"]],
    }
    raw = {"provider": "ollama-qwen", "model": "qwen", "text": json.dumps({
        "summary": "bad", "work_units": [{"title": "x", "objective": "y", "lane_id": "CMD-07", "evidence_goal": "z", "mode": "READ_ONLY"}],
    })}
    import pytest
    with pytest.raises(ValueError, match="does not belong"):
        mod.ensure_idle_qwen_plan(pack, tmp_path, lambda _prompt: raw)


def test_seed_qwen_idle_work_is_exact_current_task_bound_and_deduplicated(tmp_path):
    mod = load_module()
    program_path = tmp_path / "TASK_PROGRAM.json"; program_path.write_text(json.dumps(program()))
    ledger_path = tmp_path / "BOOSTER_TASK_LIST.json"; ledger_path.write_text(json.dumps(ledger()))
    raw_program = program_path.read_bytes(); program_sha = hashlib.sha256(raw_program).hexdigest()
    plan = {
        "schema": "minitz.qwen_idle_boost_plan/v1", "authority": "NONE_NON_CANONICAL_WORK_COORDINATION", "progression_authority": False,
        "booster_id": "BOOST-01", "task_id": "T2", "task_revision": 3, "task_sha256": "b" * 64,
        "program_revision": 7, "program_sha256": program_sha, "context_digest": "c" * 64, "plan_digest": "d" * 64,
        "summary": "current-task read-only acceleration", "provider": "ollama-qwen", "model": "qwen", "usage": {},
        "work_units": [{"work_unit_id": "QWEN-1234567890abcdef", "title": "trace", "objective": "trace current task", "lane_id": "CMD-06", "evidence_goal": "exact refs", "mode": "READ_ONLY"}],
    }
    plan_path = tmp_path / "plan.json"; plan_path.write_text(json.dumps(plan))
    first = mod.seed_qwen_idle_work(program_path, ledger_path, plan_path)
    second = mod.seed_qwen_idle_work(program_path, ledger_path, plan_path)
    assert first["work_id"] == second["work_id"]
    saved = json.loads(ledger_path.read_text())
    rows = [row for row in saved["items"] if row.get("work_id") == first["work_id"]]
    assert len(rows) == 1
    assert rows[0]["canonical_task_id"] == "T2"
    assert rows[0]["canonical_task_revision"] == 3
    assert rows[0]["canonical_task_sha256"] == "b" * 64
    assert rows[0]["work_status"] == "QUEUED"
    assert rows[0]["write_authority"] == "READ_ONLY"
    assert rows[0]["progression_authority"] is False


def test_seed_qwen_idle_work_rejects_stale_task_identity(tmp_path):
    mod = load_module()
    program_path = tmp_path / "TASK_PROGRAM.json"; program_path.write_text(json.dumps(program()))
    ledger_path = tmp_path / "BOOSTER_TASK_LIST.json"; ledger_path.write_text(json.dumps(ledger()))
    program_sha = hashlib.sha256(program_path.read_bytes()).hexdigest()
    plan = {
        "schema": "minitz.qwen_idle_boost_plan/v1", "authority": "NONE_NON_CANONICAL_WORK_COORDINATION", "progression_authority": False,
        "booster_id": "BOOST-01", "task_id": "T2", "task_revision": 2, "task_sha256": "b" * 64,
        "program_revision": 7, "program_sha256": program_sha, "context_digest": "c" * 64, "plan_digest": "d" * 64,
        "summary": "stale", "provider": "ollama-qwen", "model": "qwen", "usage": {}, "work_units": [],
    }
    plan_path = tmp_path / "plan.json"; plan_path.write_text(json.dumps(plan))
    import pytest
    with pytest.raises(ValueError, match="stale Qwen idle plan"):
        mod.seed_qwen_idle_work(program_path, ledger_path, plan_path)

def _semantic_cache_pack():
    return {
        "schema": "minitz.booster_context/v1",
        "project_scope": "minitz",
        "booster_id": "BOOST-02",
        "domain": "Evidence",
        "authority": "NONE",
        "progression_authority": False,
        "selected_task": {
            "task_id": "T2", "revision": 3, "task_record_sha256": "b" * 64,
            "objective": {"desired_state": "prove cache semantics"},
            "acceptance": ["material changes invalidate"],
            "inputs": [{"kind": "CURRENT_SOURCE", "path": "src/a.py"}],
        },
        "ledger_entry": {
            "canonical_task_id": "T2", "canonical_task_revision": 3,
            "canonical_task_sha256": "b" * 64, "cycle_count": 1,
            "work_status": "IN_PROGRESS", "summary": "verified work",
            "files_changed": ["src/a.py"], "evidence_refs": ["e1"],
        },
        "memory": {"records": [{"content_ref": "sha256:m1", "text": "learned fact"}]},
        "projection": {"task_id": "T2", "checkpoint_ref": "cp1"},
        "incoming_handoffs": [],
        "canonical_program": {"revision": 7, "sha256": "1" * 64,
                              "current_execution": {"task_id": "OTHER"}},
        "services": {"primary_local": "qwen", "external_loop_state": "IDLE"},
        "sandbox": {"host_workspace": "/old/path", "normal_network": "NONE"},
    }


def test_context_digest_ignores_unrelated_global_runtime_churn():
    mod = load_module()
    base = _semantic_cache_pack()
    changed = json.loads(json.dumps(base))
    changed["canonical_program"] = {
        "revision": 99, "sha256": "f" * 64,
        "current_execution": {"task_id": "UNRELATED", "task_revision": 12},
    }
    changed["services"] = {"primary_local": "different", "external_loop_state": "BUSY"}
    changed["sandbox"] = {"host_workspace": "/new/path", "normal_network": "CHANGED"}
    changed["ledger_entry"].update({
        "cycle_count": 88, "last_claimed_at": "later", "updated_at": "later",
        "work_status": "HANDOFF_READY", "last_worker": "BOOST-02",
    })
    assert mod.context_digest(base) == mod.context_digest(changed)


def test_context_digest_invalidates_on_task_evidence_and_memory_material():
    mod = load_module()
    base = _semantic_cache_pack()
    baseline = mod.context_digest(base)
    changed_task = json.loads(json.dumps(base))
    changed_task["selected_task"]["revision"] = 4
    assert mod.context_digest(changed_task) != baseline
    changed_evidence = json.loads(json.dumps(base))
    changed_evidence["ledger_entry"]["evidence_refs"].append("e2")
    assert mod.context_digest(changed_evidence) != baseline
    changed_memory = json.loads(json.dumps(base))
    changed_memory["memory"]["records"].append(
        {"content_ref": "sha256:m2", "text": "new verified learning"}
    )
    assert mod.context_digest(changed_memory) != baseline


def test_ensure_local_ai_assist_promotes_matching_legacy_cache(tmp_path):
    mod = load_module()
    pack = _semantic_cache_pack()
    legacy_digest = mod._legacy_context_digest(pack)
    new_digest = mod.context_digest(pack)
    assert legacy_digest != new_digest
    cache_root = tmp_path / "cache"
    legacy = cache_root / "BOOST-02" / f"T2-{legacy_digest[:20]}.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({
        "schema": "minitz.booster_local_ai_assist/v1", "authority": "NONE",
        "progression_authority": False, "project_scope": "minitz", "booster_id": "BOOST-02", "task_id": "T2",
        "context_digest": legacy_digest, "provider": "ollama-qwen", "model": "qwen",
        "text": "reusable learned guidance", "usage": {}, "created_at": "earlier",
    }))
    calls = []
    result = mod.ensure_local_ai_assist(pack, cache_root, lambda prompt: calls.append(prompt) or {})
    assert calls == []
    assert result.name == f"T2-{new_digest[:20]}.json"
    promoted = json.loads(result.read_text())
    assert promoted["text"] == "reusable learned guidance"
    assert promoted["material_digest"] == new_digest
    assert promoted["reused_from_context_digest"] == legacy_digest


def test_context_digest_ignores_memory_order_and_projection_generation_time():
    mod = load_module()
    base = _semantic_cache_pack()
    base["memory"]["records"].append(
        {"content_ref": "sha256:m2", "text": "second learned fact"}
    )
    base["projection"]["generated_at"] = "first"
    changed = json.loads(json.dumps(base))
    changed["memory"]["records"].reverse()
    changed["projection"]["generated_at"] = "later"
    assert mod.context_digest(base) == mod.context_digest(changed)


def test_sync_files_refreshes_task_guidance_before_building_booster_contexts(tmp_path, monkeypatch):
    mod = load_module()
    program_path = tmp_path / "TASK_PROGRAM.json"; program_path.write_text(json.dumps(program()))
    ledger_path = tmp_path / "BOOSTER_TASK_LIST.json"; ledger_path.write_text(json.dumps(ledger()))
    memory_path = tmp_path / "memory.json"; memory_path.write_text(json.dumps({"records": [], "content": {}}))
    projection_path = tmp_path / "projection.json"; projection_path.write_text(json.dumps({"task_id": "T2"}))
    registry_path = tmp_path / "registry.json"; registry_path.write_text(json.dumps({"routes": {}, "providers": {}}))
    calls = []
    monkeypatch.setattr(
        mod.task_guidance, "write_guidance_documents",
        lambda path, **kwargs: calls.append((Path(path), kwargs)) or {"guide_count": 0},
    )

    mod.sync_files(program_path, ledger_path, memory_path, projection_path, registry_path, context_root=tmp_path / "contexts")

    assert calls == [(program_path, {"output_root": program_path.parent / "task_guidance", "start_offset": 6})]


def test_seed_qwen_idle_work_uses_current_task_without_legacy_current_execution(tmp_path):
    mod = load_module()
    live = program()
    live.pop("current_execution")
    live["frozen_current_task"] = {"task_id": "T2", "session_id": None}
    live["tasks"][1]["status"] = "WORKING"
    program_path = tmp_path / "TASK_PROGRAM.json"; program_path.write_text(json.dumps(live))
    ledger_path = tmp_path / "BOOSTER_TASK_LIST.json"; ledger_path.write_text(json.dumps(ledger()))
    program_sha = hashlib.sha256(program_path.read_bytes()).hexdigest()
    plan = {
        "schema": "minitz.qwen_idle_boost_plan/v1", "authority": "NONE_NON_CANONICAL_WORK_COORDINATION", "progression_authority": False,
        "booster_id": "BOOST-04", "task_id": "T2", "task_revision": 3, "task_sha256": "b" * 64,
        "program_revision": 7, "program_sha256": program_sha, "context_digest": "c" * 64, "plan_digest": "d" * 64,
        "summary": "current-task qualification", "provider": "ollama-qwen", "model": "qwen", "usage": {},
        "work_units": [{"work_unit_id": "QWEN-1234567890abcdef", "title": "validate", "objective": "validate current task", "lane_id": "CMD-07", "evidence_goal": "exact refs", "mode": "READ_ONLY"}],
    }
    plan_path = tmp_path / "plan.json"; plan_path.write_text(json.dumps(plan))
    row = mod.seed_qwen_idle_work(program_path, ledger_path, plan_path)
    assert row["canonical_task_id"] == "T2"
    assert row["canonical_task_revision"] == 3
    assert row["canonical_task_sha256"] == "b" * 64


def test_local_qwen_structured_invocation_uses_schema_and_disables_reasoning(monkeypatch):
    mod = load_module()
    seen = {}
    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps({"provider": "ollama-qwen", "model": "qwen", "text": "{}", "usage": {}})
    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return Result()
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    schema = {"name": "idle_plan", "strict": True, "schema": {"type": "object"}}
    mod._invoke_local_qwen("structured", response_schema=schema, max_tokens=512, disable_reasoning=True)
    argv = seen["argv"]
    assert argv[argv.index("--max-tokens") + 1] == "512"
    assert json.loads(argv[argv.index("--response-schema-json") + 1]) == schema
    assert "--disable-reasoning" in argv
