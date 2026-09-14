from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import json
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))
import minitz_codex_routing as routing
import minitz_production_state as state

RUNNER_SPEC = importlib.util.spec_from_file_location("runtime_correction_runner", LOCAL_AI / "minitz_production_runner.py")
assert RUNNER_SPEC and RUNNER_SPEC.loader
runner = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules[RUNNER_SPEC.name] = runner
RUNNER_SPEC.loader.exec_module(runner)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, LOCAL_AI / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "Config").mkdir()
    (project / "Config/DefaultEngine.ini").write_text("[Renderer]\nr.Test=1\n")
    return project


def _failure_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# FIX-01 — simple-task resource classification.
def test_clean_simple_exact_shell_task_uses_deterministic_path():
    decision = routing.classify_simple_operation(
        "simple", deterministic_command="printf exact", grounded_context=True,
        local_qwen_resident=True, spark_available=True, read_only_microanalysis=True,
    )
    assert decision.kind == "DETERMINISTIC"
    assert decision.command == "printf exact"


def test_clean_simple_grounded_logic_can_use_qwen():
    decision = routing.classify_simple_operation(
        "simple", deterministic_command=None, grounded_context=True,
        local_qwen_resident=True, spark_available=True, read_only_microanalysis=False,
    )
    assert decision.kind == "LOCAL_QWEN"


def test_exact_read_only_microanalysis_can_use_spark():
    decision = routing.classify_simple_operation(
        "simple", deterministic_command=None, grounded_context=True,
        local_qwen_resident=False, spark_available=True, read_only_microanalysis=True,
    )
    assert decision.kind == "SPARK"


def test_unsupported_helper_case_escalates_and_hard_quality_floor_stays_general():
    simple = routing.classify_simple_operation(
        "simple", deterministic_command=None, grounded_context=False,
        local_qwen_resident=False, spark_available=False, read_only_microanalysis=False,
    )
    hard = routing.classify_simple_operation(
        "hard", deterministic_command="printf exact", grounded_context=True,
        local_qwen_resident=True, spark_available=True, read_only_microanalysis=True,
    )
    assert simple.kind == "GENERAL_CODEX"
    assert hard.kind == "GENERAL_CODEX"


def test_simple_task_spark_and_qwen_remain_bounded_non_authorities():
    assert routing.is_bounded_fallback(routing.Route("gpt-5.3-codex-spark", "xhigh"))
    assert routing.is_bounded_fallback(routing.Route("qwen3-coder-next:minitz", "none", "ollama"))
    complete = runner.evidence.TaskResult("T", "COMPLETE", "helper says done", ("e",))
    normalized = runner._normalize_result_for_route(complete, routing.Route("gpt-5.3-codex-spark", "xhigh"))
    assert normalized.status == "CONTINUE"


# FIX-02 — bounded model-catalog discovery with last-known-good state.
def test_model_catalog_success_persists_last_known_good(tmp_path: Path, monkeypatch):
    cache = tmp_path / "catalog.json"
    payload = {"models": [{"slug": "gpt-test", "supported_reasoning_levels": [{"effort": "high"}]}]}
    seen = {}
    def fake_run(argv, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(payload), stderr="")
    monkeypatch.setattr(routing.subprocess, "run", fake_run)
    monkeypatch.setattr(routing, "_discover_local_ollama_models", lambda: set())
    result = routing.discover_catalog(cache_path=cache, timeout_seconds=0.25)
    assert result == {"gpt-test": {"high"}}
    assert seen["timeout"] == pytest.approx(0.25)
    stored = json.loads(cache.read_text())
    assert stored["state"] == "LIVE_DISCOVERED"
    assert stored["catalog_digest"]


def test_hanging_catalog_probe_reuses_valid_cache(tmp_path: Path, monkeypatch):
    cache = tmp_path / "catalog.json"
    routing.persist_catalog_cache(cache, {"gpt-cache": {"xhigh"}}, state="LIVE_DISCOVERED")
    monkeypatch.setattr(routing.subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(subprocess.TimeoutExpired("codex", 0.01)))
    monkeypatch.setattr(routing, "_discover_local_ollama_models", lambda: set())
    assert routing.discover_catalog(cache_path=cache, timeout_seconds=0.01) == {"gpt-cache": {"xhigh"}}
    assert json.loads(cache.read_text())["state"] == "LAST_KNOWN_GOOD"


def test_invalid_catalog_cache_is_rejected_and_static_fallback_survives(tmp_path: Path, monkeypatch):
    cache = tmp_path / "catalog.json"
    cache.write_text('{"schema":"wrong","catalog":{"gpt-bad":["high"]}}')
    monkeypatch.setattr(routing.subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(subprocess.TimeoutExpired("codex", 0.01)))
    monkeypatch.setattr(routing, "_discover_local_ollama_models", lambda: set())
    result = routing.discover_catalog(cache_path=cache, timeout_seconds=0.01)
    assert result == routing.fallback_catalog()
    assert "gpt-bad" not in result


def test_catalog_probe_never_mutates_active_task_or_session(tmp_path: Path, monkeypatch):
    telemetry = {"task_id": "D17-02", "task_session_id": "session-x", "cooldowns": {}}
    before = json.loads(json.dumps(telemetry))
    monkeypatch.setattr(routing.subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(subprocess.TimeoutExpired("codex", 0.01)))
    monkeypatch.setattr(routing, "_discover_local_ollama_models", lambda: set())
    routing.discover_catalog(cache_path=tmp_path / "missing.json", timeout_seconds=0.01)
    assert telemetry == before


# FIX-03 — helper failure taxonomy.
def test_qwen_timeout_is_helper_deadline_exceeded(tmp_path: Path, monkeypatch):
    project = _project(tmp_path)
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"T","task_memory":{"task_class":"hard","summary":"Inspect Config/DefaultEngine.ini"},"failures":[],"capabilities":{}}))
    monkeypatch.setattr(runner.subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(subprocess.TimeoutExpired("qwen", 90, output="partial")))
    journal = runner.production_events.ProductionEventJournal(tmp_path/"events.jsonl", failure_path=tmp_path/"failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path, "T", projection, journal, project_root=project) is None
    row = _failure_rows(tmp_path/"failures.jsonl")[-1]
    assert row["failure_type"] == "HELPER_DEADLINE_EXCEEDED"
    assert row["helper_budget_seconds"] == 110
    assert row["elapsed_seconds"] >= 0


def test_qwen_nonzero_exit_is_process_failed(tmp_path: Path, monkeypatch):
    project = _project(tmp_path)
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"T","task_memory":{"task_class":"hard","summary":"Inspect Config/DefaultEngine.ini"},"failures":[],"capabilities":{}}))
    monkeypatch.setattr(runner.subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 7, stdout="raw", stderr="bad exit"))
    journal = runner.production_events.ProductionEventJournal(tmp_path/"events.jsonl", failure_path=tmp_path/"failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path, "T", projection, journal, project_root=project) is None
    assert _failure_rows(tmp_path/"failures.jsonl")[-1]["failure_type"] == "PROCESS_FAILED"


def test_qwen_bad_json_is_invalid_result(tmp_path: Path, monkeypatch):
    project = _project(tmp_path)
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"T","task_memory":{"task_class":"hard","summary":"Inspect Config/DefaultEngine.ini"},"failures":[],"capabilities":{}}))
    monkeypatch.setattr(runner.subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout="not-json", stderr=""))
    journal = runner.production_events.ProductionEventJournal(tmp_path/"events.jsonl", failure_path=tmp_path/"failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path, "T", projection, journal, project_root=project) is None
    assert _failure_rows(tmp_path/"failures.jsonl")[-1]["failure_type"] == "INVALID_RESULT"


def test_qwen_invented_path_is_validation_rejected(tmp_path: Path, monkeypatch):
    project = _project(tmp_path)
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"T","task_memory":{"task_class":"hard","summary":"Inspect Config/DefaultEngine.ini"},"failures":[],"capabilities":{}}))
    envelope = {"provider":"ollama-qwen","model":"qwen","text":"Inspect `invented/path.cpp`.","usage":{}}
    monkeypatch.setattr(runner.subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout=json.dumps(envelope), stderr=""))
    journal = runner.production_events.ProductionEventJournal(tmp_path/"events.jsonl", failure_path=tmp_path/"failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path, "T", projection, journal, project_root=project) is None
    assert _failure_rows(tmp_path/"failures.jsonl")[-1]["failure_type"] == "VALIDATION_REJECTED"


def test_spark_timeout_is_helper_deadline_exceeded(tmp_path: Path, monkeypatch):
    project = _project(tmp_path)
    local = tmp_path / "local.json"; local.write_text(json.dumps({"text":"Inspect `Config/DefaultEngine.ini`."}))
    task = state.TaskRecord("T", "hard", "Inspect renderer", "PENDING")
    monkeypatch.setattr(runner, "_bounded_packet_id", lambda *_a: "state-1")
    monkeypatch.setattr(runner.subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(subprocess.TimeoutExpired("spark", 180, output="partial")))
    journal = runner.production_events.ProductionEventJournal(tmp_path/"events.jsonl", failure_path=tmp_path/"failures.jsonl")
    assert runner._ensure_taskbooster_assist(tmp_path, project, tmp_path, task, routing.Route("gpt-6-astra","ultra"), {"gpt-5.3-codex-spark":{"xhigh"}}, local, journal) is None
    row = _failure_rows(tmp_path/"failures.jsonl")[-1]
    assert row["failure_type"] == "HELPER_DEADLINE_EXCEEDED"
    assert row["helper_budget_seconds"] == 180


def test_helper_timeout_does_not_create_model_cooldown():
    telemetry = runner.initial_runtime()
    before = dict(telemetry["cooldowns"])
    assert runner._helper_failure_cools_model("HELPER_DEADLINE_EXCEEDED") is False
    assert telemetry["cooldowns"] == before


# FIX-04 — independent staged audit execution.
def test_staged_audit_failure_does_not_suppress_remaining_stages(tmp_path: Path):
    audit = _load("minitz_staged_audit")
    ran: list[str] = []
    def fail_stage():
        ran.append("fail"); raise RuntimeError("boom")
    def pass_stage():
        ran.append("pass"); return audit.StageOutcome("PASS", ("evidence:ok",))
    receipt = audit.run_staged_audit([
        audit.AuditStage("GIT_SOURCE_FINGERPRINT", fail_stage),
        audit.AuditStage("D17_CONTINUITY", pass_stage),
    ])
    assert ran == ["fail", "pass"]
    assert [row["stage_id"] for row in receipt["stages"]] == ["GIT_SOURCE_FINGERPRINT", "D17_CONTINUITY"]
    assert receipt["result"] == "FAIL"
    assert receipt["authority"] == "NONE"
    assert receipt["mutation_authority"] is False


def test_staged_audit_preserves_stage_exit_status_and_partial_unknown():
    audit = _load("minitz_staged_audit")
    receipt = audit.run_staged_audit([
        audit.AuditStage("SERVICE_READBACK", lambda: audit.StageOutcome("PASS", (), exit_status=0)),
        audit.AuditStage("GPU_READBACK", lambda: audit.StageOutcome("UNKNOWN", ("gpu unavailable",), exit_status=4, failure_type="RESOURCE_UNAVAILABLE")),
    ])
    assert receipt["result"] == "PARTIAL"
    assert receipt["stages"][1]["exit_status"] == 4
    assert receipt["stages"][1]["failure_type_if_any"] == "RESOURCE_UNAVAILABLE"


# FIX-05 — private secret leak verifier.
def test_private_secret_verifier_safe_and_leak_fixtures(tmp_path: Path):
    verifier = _load("minitz_private_secret_verifier")
    secret = tmp_path / "runtime.env"; secret.write_text("TOKEN=super-private-value-123\n")
    safe = tmp_path / "safe.txt"; safe.write_text("ordinary public evidence")
    leak = tmp_path / "leak.txt"; leak.write_text("prefix super-private-value-123 suffix")
    safe_receipt = verifier.verify_secret_leaks(secret, [safe])
    leak_receipt = verifier.verify_secret_leaks(secret, [leak])
    assert safe_receipt["result"] == "PASS" and safe_receipt["exact_value_hit_count"] == 0
    assert leak_receipt["result"] == "FAIL" and leak_receipt["exact_value_hit_count"] == 1
    assert "super-private-value-123" not in json.dumps(safe_receipt)
    assert "super-private-value-123" not in json.dumps(leak_receipt)


def test_private_secret_verifier_ignores_invalid_short_api_key_placeholders(tmp_path: Path):
    verifier = _load("minitz_private_secret_verifier")
    env = tmp_path / "runtime.env"
    env.write_text("GEMINI_API_KEY=abcd\nMINITZ_GOOGLE_API_KEY=abcd\nCLIENT_SECRET=real-secret-value-12345\n")
    target = tmp_path / "helper.sh"
    target.write_text("ordinary abcd placeholder text")
    receipt = verifier.verify_secret_leaks(env, [target])
    assert receipt["result"] == "PASS"
    assert receipt["schema"] == "minitz.private_secret_leak_receipt/v3"
    assert receipt["verifier_version"] == "3"
    assert receipt["secret_entry_count"] == 1
    assert receipt["exact_value_hit_count"] == 0


def test_private_secret_verifier_failure_is_unknown(tmp_path: Path):
    verifier = _load("minitz_private_secret_verifier")
    target = tmp_path / "safe.txt"; target.write_text("safe")
    receipt = verifier.verify_secret_leaks(tmp_path / "missing.env", [target])
    assert receipt["result"] == "UNKNOWN"
    assert receipt["exact_value_hit_count"] is None


def test_simple_post_selection_assists_do_not_repeat_preselection_helpers(tmp_path: Path, monkeypatch):
    project = _project(tmp_path); runtime = tmp_path / "runtime"; runtime.mkdir()
    projection = runtime / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"T","task_memory":{"task_class":"simple","summary":"Inspect `Config/DefaultEngine.ini`."},"failures":[],"capabilities":{}}))
    task = state.TaskRecord("T", "simple", "Inspect renderer", "PENDING")
    calls: list[str] = []
    monkeypatch.setattr(runner, "_ensure_local_resource_assist", lambda *_a, **_k: calls.append("qwen"))
    monkeypatch.setattr(runner, "_ensure_taskbooster_assist", lambda *_a, **_k: calls.append("spark"))
    result = runner._prepare_optional_task_assists(
        tmp_path, project, runtime, task, routing.Route("gpt-5.6-luna","medium"),
        {"gpt-5.3-codex-spark":{"xhigh"}}, projection,
    )
    assert result == (None, None)
    assert calls == []


def test_private_secret_verifier_cli_never_prints_secret_literal(tmp_path: Path):
    secret_value = "super-private-cli-value-456"
    secret = tmp_path / "runtime.env"; secret.write_text(f"TOKEN={secret_value}\n")
    target = tmp_path / "safe.txt"; target.write_text("safe")
    receipt = tmp_path / "receipt.json"
    proc = subprocess.run([
        sys.executable, str(LOCAL_AI / "minitz_private_secret_verifier.py"),
        "--secret-source", str(secret), "--target", str(target), "--receipt", str(receipt),
    ], text=True, capture_output=True, check=False)
    assert proc.returncode == 0
    assert secret_value not in proc.stdout and secret_value not in proc.stderr
    assert secret_value not in receipt.read_text()


def test_simple_route_runtime_orders_qwen_spark_then_general(tmp_path: Path, monkeypatch):
    project = _project(tmp_path)
    task = state.TaskRecord("T", "simple", "Inspect `Config/DefaultEngine.ini` read-only.", "PENDING")
    catalog = {
        "qwen3-coder-next:minitz": {"local"}, "gpt-5.3-codex-spark": {"xhigh"},
        "gpt-5.6-luna": {"medium"},
    }
    telemetry: dict[str, object] = {}
    monkeypatch.setattr(runner, "_local_qwen_resident", lambda: True)
    first, packet = runner._select_task_route(task, catalog, {}, datetime.now(timezone.utc), telemetry, tmp_path, project)
    assert first == routing.Route("qwen3-coder-next:minitz", "none", "ollama")
    assert packet
    runner._record_simple_helper_attempt(telemetry, task.id, packet, first)
    second, packet2 = runner._select_task_route(task, catalog, {}, datetime.now(timezone.utc), telemetry, tmp_path, project)
    assert second == routing.Route("gpt-5.3-codex-spark", "xhigh")
    runner._record_simple_helper_attempt(telemetry, task.id, packet2, second)
    third, bounded = runner._select_task_route(task, catalog, {}, datetime.now(timezone.utc), telemetry, tmp_path, project)
    assert third == routing.Route("gpt-5.6-luna", "medium")
    assert bounded is None


def test_simple_route_without_grounded_scope_goes_general(tmp_path: Path, monkeypatch):
    project = _project(tmp_path)
    task = state.TaskRecord("T", "simple", "Summarize current state", "PENDING")
    catalog = {
        "qwen3-coder-next:minitz": {"local"}, "gpt-5.3-codex-spark": {"xhigh"},
        "gpt-5.6-luna": {"medium"},
    }
    monkeypatch.setattr(runner, "_local_qwen_resident", lambda: True)
    route, bounded = runner._select_task_route(task, catalog, {}, datetime.now(timezone.utc), {}, tmp_path, project)
    assert route == routing.Route("gpt-5.6-luna", "medium")
    assert bounded is None


def test_runtime_catalog_discovery_uses_durable_cache_and_finite_deadline(tmp_path: Path, monkeypatch):
    seen: dict[str, object] = {}
    expected = {"gpt-5.6-luna": {"medium"}}
    def fake_discover(**kwargs):
        seen.update(kwargs)
        return expected
    monkeypatch.setattr(runner.routing, "discover_catalog", fake_discover)
    assert runner._discover_runtime_catalog(tmp_path) == expected
    assert seen["cache_path"] == tmp_path / "model-catalog-cache.json"
    assert 0 < float(seen["timeout_seconds"]) <= 2.0


def test_catalog_static_fallback_records_discovery_unavailable_state(tmp_path: Path, monkeypatch):
    cache = tmp_path / "catalog.json"
    monkeypatch.setattr(
        routing.subprocess, "run",
        lambda *_a, **_k: (_ for _ in ()).throw(subprocess.TimeoutExpired("codex", 0.01)),
    )
    monkeypatch.setattr(routing, "_discover_local_ollama_models", lambda: set())
    assert routing.discover_catalog(cache_path=cache, timeout_seconds=0.01) == routing.fallback_catalog()
    payload = json.loads(cache.read_text())
    assert payload["state"] == "STATIC_FALLBACK"
    assert payload["probe_state"] == "DISCOVERY_UNAVAILABLE"
    assert payload["catalog_digest"]


def test_helper_failure_projection_keeps_budget_elapsed_and_route_metadata():
    projection = runner._assist_projection_payload({
        "task_id": "T", "task_memory": {"task_id": "T", "task_class": "simple"},
        "failures": [{
            "failure_type": "HELPER_DEADLINE_EXCEEDED", "helper_budget_seconds": 90,
            "elapsed_seconds": 90.25, "provider": "ollama-qwen", "model": "qwen3-coder-next:minitz",
            "event_type": "resource.local_assist_failed",
        }],
    })
    failure = projection["failures"][-1]
    assert failure["helper_budget_seconds"] == 90
    assert failure["elapsed_seconds"] == 90.25
    assert failure["provider"] == "ollama-qwen"
    assert failure["model"] == "qwen3-coder-next:minitz"


def test_staged_audit_expected_negative_exit_can_still_pass():
    audit = _load("minitz_staged_audit")
    receipt = audit.run_staged_audit([
        audit.AuditStage("SERVICE_READBACK", lambda: audit.StageOutcome("PASS", ("inactive as expected",), exit_status=3)),
        audit.AuditStage("PROCESS_READBACK", lambda: audit.StageOutcome("PASS", ("no child expected",), exit_status=1)),
    ])
    assert receipt["result"] == "PASS"
    assert [row["exit_status"] for row in receipt["stages"]] == [3, 1]


def test_staged_audit_receipt_is_immutable_and_idempotent(tmp_path: Path):
    audit = _load("minitz_staged_audit")
    receipt = audit.run_staged_audit([
        audit.AuditStage("GIT_SOURCE_FINGERPRINT", lambda: audit.StageOutcome("PASS", ("git:abc",))),
    ])
    path = tmp_path / "receipt.json"
    audit.write_receipt(path, receipt)
    first = path.read_bytes()
    audit.write_receipt(path, receipt)
    assert path.read_bytes() == first
    changed = dict(receipt); changed["result"] = "FAIL"
    with pytest.raises(FileExistsError):
        audit.write_receipt(path, changed)


def test_private_secret_verifier_empty_secret_source_is_unknown(tmp_path: Path):
    verifier = _load("minitz_private_secret_verifier")
    secret = tmp_path / "runtime.env"; secret.write_text("# no configured entries\n")
    target = tmp_path / "safe.txt"; target.write_text("safe")
    receipt = verifier.verify_secret_leaks(secret, [target])
    assert receipt["result"] == "UNKNOWN"
    assert receipt["exact_value_hit_count"] is None


def test_private_secret_verifier_ignores_ordinary_config_values(tmp_path: Path):
    verifier = _load("minitz_private_secret_verifier")
    secret_value = "fixture-secret-value-901"
    env = tmp_path / "runtime.env"
    env.write_text(
        "HOST=localhost\nPORT=11434\n"
        f"API_TOKEN={secret_value}\n"
    )
    target = tmp_path / "target.txt"
    target.write_text("localhost localhost 11434 ordinary evidence")
    receipt = verifier.verify_secret_leaks(env, [target])
    assert receipt["result"] == "PASS"
    assert receipt["secret_entry_count"] == 1
    assert receipt["config_entry_count"] == 2
    assert receipt["exact_value_hit_count"] == 0
    rendered = json.dumps(receipt)
    assert secret_value not in rendered
    assert "API_TOKEN" not in rendered and "HOST" not in rendered


def test_private_secret_verifier_detects_secret_in_mixed_env(tmp_path: Path):
    verifier = _load("minitz_private_secret_verifier")
    secret_value = "fixture-secret-value-902"
    env = tmp_path / "runtime.env"
    env.write_text(
        "MODEL=qwen3-coder-next:minitz\n"
        f"CLIENT_SECRET={secret_value}\n"
    )
    target = tmp_path / "target.txt"
    target.write_text("prefix " + secret_value + " suffix")
    receipt = verifier.verify_secret_leaks(env, [target])
    assert receipt["result"] == "FAIL"
    assert receipt["secret_entry_count"] == 1
    assert receipt["config_entry_count"] == 1
    assert receipt["exact_value_hit_count"] == 1
    rendered = json.dumps(receipt)
    assert secret_value not in rendered
    assert "CLIENT_SECRET" not in rendered and "MODEL" not in rendered


def test_private_secret_verifier_classifies_sensitive_keys_not_all_runtime_config(tmp_path: Path):
    verifier = _load("minitz_private_secret_verifier")
    secret = tmp_path / "runtime.env"
    secret.write_text(
        "PORT=443\nMODE=production\nHOST=127.0.0.1\n"
        "API_TOKEN=super-private-sensitive-value-789\n"
    )
    target = tmp_path / "public.txt"
    target.write_text("production on 127.0.0.1 port 443")
    receipt = verifier.verify_secret_leaks(secret, [target])
    assert receipt["result"] == "PASS"
    assert receipt["secret_entry_count"] == 1
    assert receipt["config_entry_count"] == 3
    assert receipt["exact_value_hit_count"] == 0
    assert "super-private-sensitive-value-789" not in json.dumps(receipt)


def test_private_secret_verifier_detects_sensitive_key_value_even_with_ordinary_config(tmp_path: Path):
    verifier = _load("minitz_private_secret_verifier")
    secret = tmp_path / "runtime.env"
    secret.write_text("MODE=production\nCLIENT_SECRET=super-private-client-secret-321\n")
    target = tmp_path / "leak.txt"
    target.write_text("prefix super-private-client-secret-321 suffix")
    receipt = verifier.verify_secret_leaks(secret, [target])
    assert receipt["result"] == "FAIL"
    assert receipt["secret_entry_count"] == 1
    assert receipt["config_entry_count"] == 1
    assert receipt["exact_value_hit_count"] == 1


def test_private_secret_verifier_parses_multiline_quoted_secret_without_unknown(tmp_path: Path):
    verifier = _load("minitz_private_secret_verifier")
    secret = tmp_path / "runtime.env"
    secret.write_text('CLIENT_SECRET="alpha-sensitive\nbeta-sensitive\ngamma-sensitive"\nMODE=production\n')
    target = tmp_path / "safe.txt"; target.write_text("ordinary public evidence")
    receipt = verifier.verify_secret_leaks(secret, [target])
    assert receipt["result"] == "PASS"
    assert receipt["secret_entry_count"] == 1
    assert receipt["config_entry_count"] == 1
    assert receipt["unknown_entry_count"] == 0
    assert receipt["exact_value_hit_count"] == 0
