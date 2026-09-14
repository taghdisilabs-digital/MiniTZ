from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/local-ai"))
spec = importlib.util.spec_from_file_location("commander_repair_runner", ROOT / "ops/local-ai/biella_production_runner.py")
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


def collect(tmp_path, stdout, stderr="", rc=0):
    paths = runner._commander_paths(tmp_path, "repair-test")
    paths[0].parent.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(stdout)
    paths[1].write_text(stderr)
    handle = runner.CommanderHandle("repair-test", "CMD-01", "requirements", "ollama-qwen", "minitz", "T", "a" * 64, "b" * 64, SimpleNamespace(poll=lambda: rc), *paths)
    runner._collect_commander_assists(tmp_path, {handle.key: handle})
    return handle


@pytest.mark.parametrize("text", ["HTTP_402 payment required", "HTTP_429 rate limit", "connection refused"])
def test_successful_process_content_is_not_provider_health(text):
    assert runner.commander.classify_failure(0, text) == "ACTIVE"


@pytest.mark.parametrize("text", ["HTTP_402", "HTTP_429", "connection refused"])
def test_malformed_answer_is_result_scoped(tmp_path, text):
    handle = collect(tmp_path, json.dumps({"provider": "ollama-qwen", "text": '{"historical": "' + text}))
    rejection = json.loads(handle.rejected_path.read_text())
    assert rejection["status"] == "NEEDS_MODIFICATION"
    assert rejection["failure_type"] == "INVALID_RESULT"
    assert not runner._commander_provider_health_path(tmp_path).exists()
    assert Path(rejection["raw_result_path"]).is_file()


@pytest.mark.parametrize("text", ["HTTP_402 payment required", "HTTP_429 rate limit"])
def test_real_execution_error_retains_provider_restriction(tmp_path, text):
    handle = collect(tmp_path, "", text, 2)
    assert json.loads(handle.rejected_path.read_text())["status"] == "OUT_OF_CREDIT"
    assert runner._active_commander_provider_health(tmp_path)["ollama-qwen"]["status"] == "OUT_OF_CREDIT"


def test_failed_process_generated_answer_is_not_billing_evidence(tmp_path):
    handle = collect(tmp_path, json.dumps({"provider": "ollama-qwen", "text": "historical HTTP_402"}), "local parse failure", 1)
    assert json.loads(handle.rejected_path.read_text())["status"] == "NEEDS_MODIFICATION"


def useful_result(ref="context.summary"):
    return {"lane_id": "CMD-01", "status": "USEFUL", "summary": "Preserve the sandbox boundary while repairing the result classifier.", "findings": ["Generated stdout must not determine billing status."], "evidence_refs": [ref], "candidate_actions": ["Separate process errors from result validation."], "uncertainties": []}


def test_quality_rejects_invented_evidence():
    packet = {"context": {"summary": "Generated stdout currently enters billing classification."}}
    with pytest.raises(ValueError, match="evidence"):
        runner.commander.validate_result_quality(packet, useful_result("invented/path.py"))


def test_quality_rejects_empty_useful_claim():
    result = useful_result()
    result["findings"] = []
    with pytest.raises(ValueError, match="findings"):
        runner.commander.validate_result_quality({"context": {"summary": "Observed defect"}}, result)


def test_grounded_quality_is_candidate_not_functional_acceptance():
    receipt = runner.commander.validate_result_quality({"context": {"summary": "Observed defect"}}, useful_result())
    assert receipt["status"] == "PASS"
    assert receipt["task_completion_authority"] is False
    assert receipt["functional_acceptance"] == "REQUIRES_TASK_VALIDATION"


def capacity(**changes):
    snapshot = {"ram_available_mib": 40000, "gpu_free_mib": 6800, "memory_pressure_full_avg10": 0.0}
    snapshot.update(changes)
    return runner.commander.local_capacity_admission(snapshot)


def test_local_capacity_admits_useful_work_with_reserve():
    assert capacity()["admitted"] is True


@pytest.mark.parametrize("changes,reason", [({"ram_available_mib": 1024}, "RAM_RESERVE"), ({"gpu_free_mib": 1024}, "VRAM_RESERVE"), ({"memory_pressure_full_avg10": 20.0}, "MEMORY_PRESSURE"), ({"gpu_free_mib": None}, "CAPACITY_UNKNOWN")])
def test_capacity_rejects_pressure_without_inventing_quota(changes, reason):
    result = capacity(**changes)
    assert result["admitted"] is False
    assert result["reason"] == reason
    assert "OUT_OF_CREDIT" not in json.dumps(result)


def test_local_resource_command_requires_structured_output():
    registry = json.loads((ROOT / "ops/workstation/provider-registry.json").read_text())
    command = runner._commander_resource_command(registry, "ollama-qwen")
    assert "--response-schema-json" in command
    assert "--disable-reasoning" in command


def test_collector_automatically_rejects_ungrounded_claim(tmp_path):
    paths = runner._commander_paths(tmp_path, "quality-test")
    paths[0].parent.mkdir(parents=True)
    paths[0].write_text(json.dumps({"provider": "ollama-qwen", "text": json.dumps(useful_result("invented.py"))}))
    paths[1].write_text("")
    handle = runner.CommanderHandle("quality-test", "CMD-01", "requirements", "ollama-qwen", "minitz", "T", "a"*64, "b"*64, SimpleNamespace(poll=lambda: 0), *paths, quality_context={"summary": "Observed defect"})
    runner._collect_commander_assists(tmp_path, {handle.key: handle})
    assert not handle.accepted_path.exists()
    assert json.loads(handle.rejected_path.read_text())["failure_scope"] == "RESULT"
    assert not runner._commander_provider_health_path(tmp_path).exists()


def test_collector_records_grounded_candidate_without_changing_other_provider(tmp_path):
    runner._record_commander_provider_failure(tmp_path, "cerebras", "OUT_OF_CREDIT", "HTTP_402")
    before = runner._active_commander_provider_health(tmp_path)["cerebras"]
    paths = runner._commander_paths(tmp_path, "quality-pass")
    paths[0].write_text(json.dumps({"provider": "ollama-qwen", "text": json.dumps(useful_result())}))
    paths[1].write_text("")
    handle = runner.CommanderHandle("quality-pass", "CMD-01", "requirements", "ollama-qwen", "minitz", "T", "a"*64, "b"*64, SimpleNamespace(poll=lambda: 0), *paths, quality_context={"summary": "Observed defect"})
    runner._collect_commander_assists(tmp_path, {handle.key: handle})
    assert json.loads(handle.accepted_path.read_text())["quality_validation"]["status"] == "PASS"
    assert runner._active_commander_provider_health(tmp_path)["cerebras"] == before


def launch_fixture(tmp_path, monkeypatch, snapshot):
    import test_production_runner as fixtures
    repo, project, runtime, capsule, projection, task = fixtures._commander_fixture(tmp_path)
    path = repo / "ops/workstation/provider-registry.json"
    registry = json.loads(path.read_text())
    registry["providers"]["ollama-qwen"] = {"default_model": "qwen"}
    registry["routes"]["llm.fast"].insert(0, "ollama-qwen")
    path.write_text(json.dumps(registry))
    monkeypatch.setattr(runner, "_local_qwen_resident", lambda: True)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *a, **k: ("groq",))
    monkeypatch.setattr(runner.local_capacity, "observe_local_capacity", lambda: snapshot)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: fixtures._CommanderFakeProcess())
    inflight = {}
    index = runner._launch_commander_assists(repo, project, runtime, task, "a" * 64, capsule, projection, inflight)
    return json.loads(index.read_text()), inflight, runtime


def test_scheduler_uses_free_local_capacity_before_remote_assignment(tmp_path, monkeypatch):
    snapshot = {"ram_available_mib": 40000, "gpu_free_mib": 6800, "memory_pressure_full_avg10": 0}
    monkeypatch.setattr(runner.commander, "provider_schedule", lambda lanes, *a, **k: {lane.lane_id: "groq" for lane in lanes})
    index, inflight, _ = launch_fixture(tmp_path, monkeypatch, snapshot)
    assert index["lanes"][0]["provider"] == "ollama-qwen"
    assert index["lanes"][0]["route_reason"] == "LOCAL_FIRST_WITH_CAPACITY"
    assert sum(h.requested_provider == "ollama-qwen" for h in inflight.values()) == 1


@pytest.mark.parametrize("field,value,reason", [("ram_available_mib", 512, "RAM_RESERVE"), ("gpu_free_mib", 256, "VRAM_RESERVE"), ("memory_pressure_full_avg10", 20, "MEMORY_PRESSURE")])
def test_scheduler_capacity_fallback_keeps_quota_separate(tmp_path, monkeypatch, field, value, reason):
    snapshot = {"ram_available_mib": 40000, "gpu_free_mib": 6800, "memory_pressure_full_avg10": 0}
    snapshot[field] = value
    index, inflight, runtime = launch_fixture(tmp_path, monkeypatch, snapshot)
    assert index["local_capacity"]["reason"] == reason
    assert all(h.requested_provider != "ollama-qwen" for h in inflight.values())
    assert any(h.requested_provider == "groq" for h in inflight.values())
    assert not runner._commander_provider_health_path(runtime).exists()
