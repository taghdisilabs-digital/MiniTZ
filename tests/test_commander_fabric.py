from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/minitz_commander_fabric.py"


def fabric():
    assert MODULE.exists(), "Commander fabric module is not implemented"
    spec = importlib.util.spec_from_file_location("minitz_commander_fabric", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_exactly_thirty_stable_unique_commander_lanes():
    mod = fabric()
    lanes = mod.commander_lanes()
    assert len(lanes) == 30
    assert [lane.lane_id for lane in lanes] == [f"CMD-{i:02d}" for i in range(1, 31)]
    assert len({lane.role for lane in lanes}) == 30
    assert all(lane.authority == "NONE" for lane in lanes)


def test_owner_workforce_split_is_five_drafters_two_writers_one_validator_and_read_summary_rest():
    mod = fabric()
    lanes = mod.commander_lanes()
    modes = [lane.work_mode for lane in lanes]
    assert modes.count("DRAFTER") == 5
    assert modes.count("WRITER") == 2
    assert modes.count("VALIDATOR") == 1
    assert modes.count("BOOST_READ_SUMMARY") == 22
    assert all(lane.authority == "NONE" for lane in lanes)


def test_commander_schema_has_no_progression_or_mutation_authority():
    mod = fabric()
    schema = mod.commander_result_schema()
    props = schema["properties"]
    assert props["status"]["enum"] == ["NO_FINDING", "USEFUL"]
    for forbidden in ("task_status", "complete", "commit", "patch", "write_files", "advance_task"):
        assert forbidden not in props


def test_cache_key_is_content_addressed_by_project_task_state_lane_and_provider():
    mod = fabric()
    a = mod.commander_cache_key("minitz", "UNIFY-04", "a" * 64, "b" * 64, "CMD-01", "requirements", "groq")
    b = mod.commander_cache_key("minitz", "UNIFY-04", "a" * 64, "b" * 64, "CMD-01", "requirements", "groq")
    c = mod.commander_cache_key("minitz", "UNIFY-04", "a" * 64, "b" * 64, "CMD-02", "task-boundary", "groq")
    d = mod.commander_cache_key("minitz", "UNIFY-04", "a" * 64, "b" * 64, "CMD-01", "requirements", "mistral")
    other_project = mod.commander_cache_key("customer-a", "UNIFY-04", "a" * 64, "b" * 64, "CMD-01", "requirements", "groq")
    assert a == b
    assert a != c != d
    assert a != other_project
    assert len(a) == 64


def test_external_provider_selection_protects_local_writer_and_requires_model_configuration():
    mod = fabric()
    registry = {
        "providers": {
            "ollama-qwen": {"required_env": [], "default_model": "qwen"},
            "groq": {"required_env": ["GROQ_API_KEY"], "default_model": "qwen"},
            "mistral": {"required_env": ["MISTRAL_API_KEY"], "default_model": "mistral-small-latest"},
            "openrouter": {"required_env": ["OPENROUTER_API_KEY"], "default_model": None},
            "gemini": {"required_env": ["GEMINI_API_KEY"], "default_model": None},
        },
        "routes": {"llm.fast": ["ollama-qwen", "groq", "mistral", "openrouter", "gemini"]},
    }
    env = {"GROQ_API_KEY": "secret-123", "MISTRAL_API_KEY": "secret-456", "OPENROUTER_API_KEY": "secret-789", "GEMINI_API_KEY": "abcd"}
    assert mod.eligible_external_providers(registry, env) == ("groq", "mistral")
    env["MINITZ_OPENROUTER_MODEL"] = "openai/gpt-oss-120b"
    assert mod.eligible_external_providers(registry, env) == ("groq", "mistral", "openrouter")


def test_external_provider_status_selects_three_healthy_api_providers_without_exposing_credentials():
    mod = fabric()
    registry = {
        "providers": {
            "ollama-qwen": {"default_model": "qwen"},
            "groq": {"default_model": "qwen"},
            "cerebras": {"default_model": "qwen"},
            "mistral": {"default_model": "mistral-small-latest"},
            "gemini": {"default_model": "gemini"},
        },
        "routes": {"llm.fast": ["ollama-qwen", "groq", "cerebras", "mistral", "gemini"]},
    }
    status = {"providers": [
        {"id": "groq", "state": "CONFIGURED"},
        {"id": "cerebras", "state": "CONFIGURED"},
        {"id": "mistral", "state": "CONFIGURED"},
        {"id": "gemini", "state": "NEEDS_MODIFICATION"},
    ]}
    assert mod.eligible_external_providers_from_status(registry, status, limit=3) == ("groq", "cerebras", "mistral")


def test_provider_schedule_is_deterministic_bounded_and_preserves_all_thirty_logical_lanes():
    mod = fabric()
    lanes = mod.commander_lanes()
    schedule = mod.provider_schedule(lanes, ("groq", "cerebras", "mistral"), per_provider_limit=10)
    assert len(schedule) == 30
    assert set(schedule) == {lane.lane_id for lane in lanes}
    assert list(schedule.values()).count("groq") == 10
    assert list(schedule.values()).count("cerebras") == 10
    assert list(schedule.values()).count("mistral") == 10
    short = mod.provider_schedule(lanes, ("groq",), per_provider_limit=10)
    assert sum(value is not None for value in short.values()) == 10
    assert sum(value is None for value in short.values()) == 20


def test_bounded_context_is_small_and_excludes_raw_unbounded_payloads():
    mod = fabric()
    task_memory = {
        "task_id": "UNIFY-04", "title": "Continuity", "summary": "s" * 20000,
        "evidence": ["e" * 1000 for _ in range(100)], "dirty_paths": [f"p/{i}" for i in range(1000)],
        "next_action": "continue", "task_class": "hard",
    }
    projection = {
        "task_id": "UNIFY-04", "failures": [{"failure_type": "X", "text": "f" * 5000} for _ in range(20)],
        "source_refs": [f"ref-{i}" for i in range(100)], "capabilities": {f"cap-{i}": ["x"] for i in range(100)},
    }
    packet = mod.bounded_context(task_memory, projection, maximum_bytes=6000)
    encoded = json.dumps(packet, sort_keys=True).encode()
    assert len(encoded) <= 6000
    assert packet["task_id"] == "UNIFY-04"
    assert len(packet["summary"]) < 20000
    assert len(packet["evidence"]) < 100
    assert len(packet["dirty_paths"]) < 1000


def test_prompt_is_explicitly_read_only_non_authoritative_and_strict_json():
    mod = fabric()
    lane = mod.commander_lanes()[0]
    packet = mod.commander_packet(
        lane=lane, project_scope="minitz", task_id="UNIFY-04", task_state_digest="a" * 64,
        projection_digest="b" * 64, requested_provider="groq", context={"task_id": "UNIFY-04"},
    )
    prompt = mod.commander_prompt(packet)
    for text in ("AUTHORITY: NONE", "DO_NOT_MODIFY_FILES", "DO_NOT_COMMIT_PUSH_PUBLISH", "DO_NOT_COMPLETE_OR_ADVANCE_TASK", "STRICT_JSON_ONLY"):
        assert text in prompt
    assert "CMD-01" in prompt and "requirements" in prompt


def test_result_validation_accepts_bounded_useful_result_and_rejects_extra_fields():
    mod = fabric()
    lane = mod.commander_lanes()[0]
    packet = mod.commander_packet(
        lane=lane, project_scope="minitz", task_id="T", task_state_digest="a" * 64, projection_digest="b" * 64,
        requested_provider="groq", context={"task_id": "T"},
    )
    result = {
        "lane_id": "CMD-01", "status": "USEFUL", "summary": "One concrete issue.",
        "findings": ["Check exact checkpoint overlap."], "evidence_refs": ["src/minitz_os/engine/checkpoint.py"],
        "candidate_actions": ["Add focused overlap test."], "uncertainties": [],
    }
    checked = mod.validate_commander_result(packet, result)
    assert checked == result
    with pytest.raises(ValueError):
        mod.validate_commander_result(packet, {**result, "task_status": "COMPLETE"})


def test_provider_output_parser_accepts_json_or_fenced_json():
    mod = fabric()
    body = {"lane_id":"CMD-01","status":"NO_FINDING","summary":"none","findings":[],"evidence_refs":[],"candidate_actions":[],"uncertainties":[]}
    payload = {"provider":"groq","model":"x","text":json.dumps(body),"usage":{}}
    parsed, meta = mod.parse_resource_result(json.dumps(payload))
    assert parsed == body and meta["provider"] == "groq"
    payload["text"] = "```json\n" + json.dumps(body) + "\n```"
    parsed, _ = mod.parse_resource_result(json.dumps(payload))
    assert parsed == body


def test_four_state_failure_classification_distinguishes_quota_offline_and_bad_configuration():
    mod = fabric()
    assert mod.classify_failure(1, "quota exhausted / rate limit reached") == "OUT_OF_CREDIT"
    assert mod.classify_failure(127, "command not found") == "OFFLINE"
    assert mod.classify_failure(1, "HTTP 400 invalid api key") == "NEEDS_MODIFICATION"
    assert mod.classify_failure(0, "") == "ACTIVE"


def test_lease_staleness_uses_expiry_or_dead_pid_only():
    mod = fabric()
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    live = mod.lease_record("k", "T", "CMD-01", "groq", 123, now=now, ttl_seconds=120)
    assert mod.lease_is_stale(live, now=now + timedelta(seconds=30), pid_alive=lambda pid: pid == 123) is False
    assert mod.lease_is_stale(live, now=now + timedelta(seconds=121), pid_alive=lambda _pid: True) is True
    assert mod.lease_is_stale(live, now=now + timedelta(seconds=30), pid_alive=lambda _pid: False) is True


def test_public_summary_contains_no_private_finding_content():
    mod = fabric()
    index = {
        "schema": "minitz.commander_fabric/v1", "authority": "NONE", "task_id": "T", "total_lanes": 30,
        "lanes": [
            {"lane_id":"CMD-01","role":"requirements","status":"ACTIVE","activity":"USEFUL","provider":"groq","result_path":"/private/result.json","summary":"PRIVATE"},
            {"lane_id":"CMD-02","role":"tests","status":"NEEDS_MODIFICATION","activity":"REJECTED","provider":"mistral","result_path":"/private/rejected.json"},
        ],
    }
    public = mod.public_summary(index)
    rendered = json.dumps(public)
    assert public["total_lanes"] == 30
    assert public["status"] == "ACTIVE"
    assert public["useful"] == 1 and public["rejected"] == 1
    assert "PRIVATE" not in rendered and "/private/" not in rendered


def test_commander_resource_command_binds_lease_to_exact_provider_without_failover():
    mod = fabric()
    cmd = mod.build_resource_command("groq", max_tokens=384, minitz_bin="/usr/local/bin/minitz")
    assert cmd == [
        "/usr/local/bin/minitz", "fast-llm", "--provider", "groq",
        "--max-tokens", "384", "--max-failover-attempts", "1",
    ]



def test_commander_resource_command_can_bind_structured_output_contract():
    mod = fabric()
    schema = mod.commander_result_schema()
    cmd = mod.build_resource_command(
        "cloudflare", max_tokens=512, minitz_bin="/usr/local/bin/minitz",
        response_schema=schema, disable_reasoning=True,
    )
    assert cmd[:7] == [
        "/usr/local/bin/minitz", "fast-llm", "--provider", "cloudflare",
        "--max-tokens", "512", "--max-failover-attempts",
    ]
    assert "--response-schema-json" in cmd
    encoded = cmd[cmd.index("--response-schema-json") + 1]
    assert json.loads(encoded) == schema
    assert "--disable-reasoning" in cmd

def test_provider_pool_skips_backed_off_candidates_and_keeps_three_when_fallback_exists():
    mod = fabric()
    pool = mod.select_provider_pool(("groq", "cerebras", "mistral", "gemini"), {"cerebras", "mistral"}, limit=3)
    assert pool == ("groq", "gemini")
    assert mod.select_provider_pool(("groq",), {"groq"}, limit=3) == ("groq",)


def test_rate_limit_retry_is_short_while_payment_exhaustion_stays_long():
    mod = fabric()
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    assert mod.failure_retry_after("OUT_OF_CREDIT", now=now, detail="groq:HTTP_429") == (now + timedelta(seconds=60)).isoformat()
    assert mod.failure_retry_after("OUT_OF_CREDIT", now=now, detail="cerebras:HTTP_402") == (now + timedelta(minutes=30)).isoformat()


def test_failure_retry_after_is_bounded_by_four_state_without_quota_probe():
    mod = fabric()
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    assert mod.failure_retry_after("OFFLINE", now=now) == (now + timedelta(minutes=5)).isoformat()
    assert mod.failure_retry_after("OUT_OF_CREDIT", now=now) == (now + timedelta(minutes=30)).isoformat()
    assert mod.failure_retry_after("NEEDS_MODIFICATION", now=now) == (now + timedelta(minutes=15)).isoformat()
    assert mod.failure_retry_after("ACTIVE", now=now) is None


def test_failure_classifier_maps_metered_http_payment_and_rate_limit_to_out_of_credit():
    mod = fabric()
    assert mod.classify_failure(2, "cerebras:HTTP_402") == "OUT_OF_CREDIT"
    assert mod.classify_failure(2, "groq:HTTP_429") == "OUT_OF_CREDIT"


def test_bounded_context_preserves_owner_correction_guard_when_supplied():
    mod = fabric()
    owner = {
        "revision": 7,
        "instruction_sha256": "a" * 64,
        "correction_precedence": "LATEST_OWNER_CORRECTION_INVALIDATES_CONFLICTING_ASSUMPTIONS",
    }
    context = mod.bounded_context(
        {"task_id": "T", "title": "Task", "summary": "same"},
        {"task_id": "T"}, owner_instruction=owner,
    )
    assert context["owner_instruction"] == owner
