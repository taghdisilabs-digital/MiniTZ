from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/workstation"))
spec = importlib.util.spec_from_file_location("minitz_quality_resource_test", ROOT / "ops/workstation/biella-resource.py")
resource = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resource)


def registry():
    return {"providers": {
        "ollama-qwen": {"default_model": "local-test", "chat_url": "http://local/v1/chat/completions"},
        "groq": {"default_model": "remote-test", "chat_url": "https://remote.invalid/chat", "required_env": ["GROQ_API_KEY"]},
    }, "routes": {"llm.fast": ["ollama-qwen", "groq"]}}


def response(text):
    return {"choices": [{"message": {"content": text}}]}


def test_nonempty_without_evaluator_is_not_quality_pass():
    result = resource.run_fast_llm(registry(), "task", provider="groq", env={"GROQ_API_KEY": "test"}, transport=lambda *a: response("success"))
    assert result["quality"]["verdict"] == "UNVALIDATED"


def test_quality_failure_falls_back_without_accepting_wrong_output():
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append(url)
        return response("wrong" if len(calls) == 1 else "correct")
    result = resource.run_fast_llm(registry(), "task", env={"GROQ_API_KEY": "test"}, transport=transport,
        local_admission=lambda: {"allowed": True},
        quality_validator=lambda text: {"verdict": "PASS" if text == "correct" else "FAIL", "evaluator": "exact.v1"})
    assert result["text"] == "correct"
    assert result["provider"] == "groq"
    assert result["quality"]["verdict"] == "PASS"
    assert result["routing_evidence"]["attempted"][0]["failure_code"] == "QUALITY_REJECTED"


def test_pressure_rejects_only_local_and_uses_configured_fallback():
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append(url)
        return response("correct")
    result = resource.run_fast_llm(registry(), "task", env={"GROQ_API_KEY": "test"}, transport=transport,
        local_admission=lambda: {"allowed": False, "reasons": ["RAM_RESERVE"]})
    assert calls == ["https://remote.invalid/chat"]
    assert result["routing_evidence"]["attempted"][0]["failure_code"] == "LOCAL_CAPACITY"


def test_local_quality_pass_keeps_local_route():
    result = resource.run_fast_llm(registry(), "task", env={"GROQ_API_KEY": "test"}, transport=lambda *a: response("correct"),
        local_admission=lambda: {"allowed": True}, quality_validator=lambda text: {"verdict": "PASS", "evaluator": "fixture.v1"})
    assert result["provider"] == "ollama-qwen"
    assert result["routing_evidence"]["fallback_used"] is False


def test_capacity_observations_and_unknowns_are_not_green():
    import minitz_local_quality as quality
    good = {"host_available_bytes": 8 * 1024**3, "cgroup_headroom_bytes": 8 * 1024**3,
        "memory_full_avg10": 0.0, "memory_some_avg10": 0.0, "gpu_free_mib": 2048, "gpu_utilization_percent": 0}
    assert quality.admit(good)["allowed"] is True
    for key, value in [("host_available_bytes", 1024), ("cgroup_headroom_bytes", 1024),
                       ("memory_full_avg10", 20), ("gpu_free_mib", 10), ("host_available_bytes", None)]:
        assert quality.admit({**good, key: value})["allowed"] is False, key
    assert quality.admit({**good, "gpu_utilization_percent": 95})["allowed"] is True


def test_exact_json_evaluator_rejects_wrong_types_extra_fields_and_self_claims():
    import minitz_local_quality as quality
    evaluate = quality.exact_json_evaluator({"host_mutation": False, "count": 3})
    assert evaluate('{"host_mutation":false,"count":3}')["verdict"] == "PASS"
    for wrong in ['{"host_mutation":true,"count":3}', '{"host_mutation":0,"count":3}',
                  '{"host_mutation":false,"count":3,"success":true}', 'success', '{"host_mutation":false,"count":2}']:
        assert evaluate(wrong)["verdict"] == "FAIL"


def test_checked_cache_reuses_revalidates_and_invalidates_only_material_input(tmp_path):
    import minitz_local_quality as quality
    calls = []
    def execute(prompt):
        calls.append(prompt)
        return {"text": '{"answer":3}', "provider": "local", "model": "observed-model"}
    identity = {"model_digest": "one", "profile": "current"}
    first = quality.checked_cached_call("work", {"answer": 3}, identity, tmp_path, execute)
    second = quality.checked_cached_call("work", {"answer": 3}, identity, tmp_path, execute)
    assert first["cache_hit"] is False and second["cache_hit"] is True
    assert len(calls) == 1
    quality.checked_cached_call("changed material input", {"answer": 3}, identity, tmp_path, execute)
    assert len(calls) == 2
    quality.checked_cached_call("work", {"answer": 3}, {**identity, "model_digest": "two"}, tmp_path, execute)
    assert len(calls) == 3


def test_failed_quality_is_not_cached_as_success(tmp_path):
    import minitz_local_quality as quality
    with pytest.raises(ValueError, match="quality"):
        quality.checked_cached_call("work", {"answer": 3}, {}, tmp_path, lambda _: {"text": '{"answer":4}'})
    assert not list(tmp_path.glob("*.json"))


def test_sandbox_runtime_cannot_mutate_host_os_or_expose_docker_socket():
    text = (ROOT / "ops/workstation/minitz-os-sandbox/runtime.sh").read_text()
    assert "systemctl" not in text
    assert "--privileged" not in text
    assert "/var/run/docker.sock" not in text
    assert "--memory" in text and "--memory-swap" in text
    assert "/resources/models:ro" in text
    assert "/usr/local/bin/ollama:ro" in text
    assert "$SANDBOX/workspace:/workspace:rw" in text
    for forbidden in ("/etc:/etc:rw", "/usr:/usr:rw", "/boot:/boot:rw", "/lib:/lib:rw"):
        assert forbidden not in text
    assert "minitz-os-lab:ubuntu26.04" in text


def test_quality_rejection_preserves_exact_failed_result_for_bounded_repair():
    with pytest.raises(resource.ResourceError) as failure:
        resource.run_fast_llm(registry(), "task", env={"GROQ_API_KEY": "test"},
            provider="groq", max_failover_attempts=1, transport=lambda *a: response("wrong"),
            quality_validator=lambda _: {"verdict": "FAIL", "evaluator": "fixture.v1"})
    detail = failure.value.evidence["attempted"][0]["evidence"]
    assert detail["result"]["text"] == "wrong"
    assert detail["quality"]["verdict"] == "FAIL"


@pytest.mark.parametrize("mode", ["READ_ONLY", "MUTATING_EXECUTION"])
def test_policy_update_preserves_authorized_active_action(mode):
    sys.path.insert(0, str(ROOT / "ops/local-ai"))
    import minitz_task_program as tasks
    active = {"task_id": "ACTIVE", "revision": 4, "status": "WORKING", "write_scope": {"execution_root": "/workspace/repo"}}
    result = tasks.resolve_effective_action(active, active_mode=mode)
    assert result["action_mode"] == mode and result["should_resume"] is True
    assert result["task_id"] == "ACTIVE" and result["task_revision"] == 4
    assert active["status"] == "WORKING"


def test_explicit_stop_and_absent_authority_do_not_invent_permission():
    sys.path.insert(0, str(ROOT / "ops/local-ai"))
    import minitz_task_program as tasks
    active = {"task_id": "ACTIVE", "revision": 4, "status": "WORKING"}
    assert tasks.resolve_effective_action(active, active_mode="MUTATING_EXECUTION", disposition="PAUSE")["should_resume"] is False
    assert tasks.resolve_effective_action(None, active_mode="MUTATING_EXECUTION")["action_mode"] == "UNKNOWN"
    assert tasks.resolve_effective_action(active, active_mode=None)["action_mode"] == "UNKNOWN"


def test_capacity_denial_is_not_mislabeled_as_bad_output_quality():
    spec = importlib.util.spec_from_file_location("startup_quality_test", ROOT / "ops/workstation/minitz-os-sandbox/startup.py")
    startup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(startup)
    failure = resource.ResourceError("capacity", evidence={"attempted": [{"failure_code": "LOCAL_CAPACITY"}]})
    assert startup.route_failure_record("test", failure, {})["quality"]["verdict"] == "NOT_EVALUATED"


@pytest.mark.parametrize("wrapped", [False, True])
def test_response_schema_is_sent_inside_the_required_named_schema_envelope(wrapped):
    raw={"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"],"additionalProperties":False}
    envelope={"name":"minitz_response","strict":True,"schema":raw}
    seen=[]
    def transport(method,url,headers,body,timeout):
        seen.append(body)
        return response('{"ok":true}')
    resource.run_fast_llm(registry(),"current task",provider="ollama-qwen",env={},
        local_admission=lambda:{"allowed":True},transport=transport,
        response_schema=envelope if wrapped else raw)
    assert seen[0]["response_format"]=={"type":"json_schema","json_schema":envelope}


def test_sandbox_runs_bounded_commanders_and_reuses_test_environment():
    text=(ROOT/"ops/workstation/minitz-os-sandbox/runtime.sh").read_text()
    assert "MINITZ_COMMANDER_AUTOLAUNCH=1" in text
    assert "MINITZ_COMMANDER_AUTOLAUNCH=0" not in text
    assert "VIRTUAL_ENV=/state/validation/startup-foundation-venv" in text
