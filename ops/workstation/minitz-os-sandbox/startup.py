#!/usr/bin/env python3
"""Sandbox foundation startup: read authority, serve local resource, qualify output.

The existing canonical executor owns task progression after the authorized launch.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ops/workstation"))
sys.path.insert(0, str(ROOT / "ops/local-ai"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import attachments as startup_attachments
import minitz_local_quality as quality
import minitz_task_program as tasks

STATE = Path("/state/runtime")
EVIDENCE = Path("/state/qualification/sandbox-foundation.json")
BASE = "http://127.0.0.1:11434"


def get_json(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as response:
        return json.load(response)


def persist(payload):
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    temporary = EVIDENCE.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(EVIDENCE)


def cases(task_id):
    return [
        ("owner-continuity", "An authorized FIX of " + task_id + " is unfinished. The owner then changes RAM/cache policy, with no cancellation. MiniTZ must be OFF before source edits. Host Ubuntu 24.04 must not change; Ubuntu 26.04 is the sandbox. Return JSON with effective_mode (READ_ONLY or MUTATING_EXECUTION), task_id, stop_before_edit (boolean), mutate_host (boolean).",
         {"effective_mode": "MUTATING_EXECUTION", "task_id": task_id, "stop_before_edit": True, "mutate_host": False}),
        ("cache-and-current-evidence", "An accepted source artifact and all relevant input digests are unchanged. The GPU-use snapshot is old. Return JSON with reuse_artifact, reobserve_gpu, rerun_all as booleans. Reuse valid durable results, observe volatile facts currently, never redo unrelated valid work.",
         {"reuse_artifact": True, "reobserve_gpu": True, "rerun_all": False}),
        ("source-conflict-regression", "Both specific commits formerly reported as conflicting are proven ancestors of current main. Remote transport is unavailable, so current remote freshness cannot be observed. Do not reopen a resolved conflict or invent fresh remote state. Return JSON: continue_local (boolean), remote_freshness (string), discard_validated_work (boolean).",
         {"continue_local": True, "remote_freshness": "UNKNOWN", "discard_validated_work": False}),
    ]


def route_failure_record(name, exc, expected):
    diagnostic = getattr(exc, "evidence", {})
    codes = [item.get("failure_code") for item in diagnostic.get("attempted", [])]
    verdict = "FAIL" if "QUALITY_REJECTED" in codes else "NOT_EVALUATED"
    return {"case": name, "quality": {"verdict": verdict}, "failure": str(exc),
            "diagnostic": diagnostic, "expected": expected, "failure_codes": codes}


def qualify(program):
    spec = importlib.util.spec_from_file_location("minitz_runtime_resource", ROOT / "ops/workstation/biella-resource.py")
    resource = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resource)
    registry = resource.load_registry(ROOT / "ops/workstation/provider-registry.json")
    model = registry["providers"]["ollama-qwen"]["default_model"]
    metadata = next(row for row in get_json("/api/tags")["models"] if row.get("name") == model or row.get("model") == model)
    profile = json.loads((ROOT / "ops/workstation/minitz-gpu-residency.json").read_text())
    identity = {"model_digest": metadata["digest"], "profile_sha256": hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()}
    samples, stop = [], threading.Event()
    def sample():
        while not stop.is_set():
            samples.append(quality.snapshot())
            stop.wait(1)
    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    results = []
    def admission():
        observed = quality.snapshot()
        resident = any(row.get("name") == model or row.get("model") == model for row in get_json("/api/ps").get("models", []))
        policy = {}
        if not resident:
            slots = profile.get("slots", [])
            if isinstance(slots, dict):
                slots = list(slots.values())
            slot = next(row for row in slots if row.get("model") == model)
            gpu_mib = int(slot["estimated_vram_mib"])
            ram = max(2 * 1024**3, int(metadata["size"]) - gpu_mib * 1024**2) + 4 * 1024**3
            policy = {"gpu_reserve_mib": gpu_mib + 512, "ram_reserve_bytes": ram, "container_reserve_bytes": ram}
        return quality.admit(observed, policy)
    try:
        for name, prompt, expected in cases(program["current_execution"]["task_id"]):
            evaluator = quality.exact_json_evaluator(expected)
            if name == "owner-continuity":
                # The explicit RUN/FIX authorization belongs to the owner.
                # Model outputs never select this action mode.
                active = tasks.task_by_id(program, program["current_execution"]["task_id"])
                action = tasks.resolve_effective_action(active, active_mode="MUTATING_EXECUTION")
                text = json.dumps({"effective_mode": action["action_mode"], "task_id": action["task_id"],
                                   "stop_before_edit": True, "mutate_host": False})
                results.append({"case": name, "provider": "deterministic-local", "model": None,
                    "text": text, "quality": evaluator(text), "cache_hit": False,
                    "negative_control": evaluator('{"success":true}')["verdict"],
                    "implementation": "minitz_task_program.resolve_effective_action"})
                continue
            schema = {"name": "minitz_task_quality", "strict": True, "schema": {
                "type": "object", "properties": {key: {"type": "boolean" if isinstance(value, bool) else "string"}
                    for key, value in expected.items()}, "required": list(expected), "additionalProperties": False}}
            if "remote_freshness" in expected:
                schema["schema"]["properties"]["remote_freshness"]["enum"] = ["CURRENT", "UNKNOWN"]
            def execute(text):
                return resource.run_fast_llm(registry, text + " Return only the JSON object, without commentary.",
                    env=dict(os.environ), provider="ollama-qwen", max_failover_attempts=1,
                    max_tokens=256, timeout=180, disable_reasoning=True,
                    local_admission=admission, quality_validator=evaluator, response_schema=schema)
            try:
                result = quality.checked_cached_call(prompt, expected, identity, Path("/state/cache/quality"), execute)
            except Exception as exc:
                results.append(route_failure_record(name, exc, expected))
                continue
            result["case"] = name
            result["negative_control"] = evaluator('{"success":true}')["verdict"]
            results.append(result)
    finally:
        stop.set()
        thread.join(timeout=5)
    final = quality.snapshot()
    return {"capability": "evidence.structured-normalization", "qualification_scope": "two exact evidence cases; owner action resolution is deterministic, not model authority",
            "results": results, "samples": samples, "current_capacity": quality.admit(final), "resident_models": get_json("/api/ps")}


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)
    program = tasks.load()
    current = program["current_execution"]
    if current is None:
        raise RuntimeError("No active canonical task")
    attachments = {}
    for name in ("compacted-memory.json", "current-task.json"):
        path = Path("/minitz-live") / name
        raw = path.read_bytes()
        value = json.loads(raw)
        attachments[name] = {"sha256": hashlib.sha256(raw).hexdigest(),
            "scope": "CURRENT_TASK" if name == "current-task.json" and current["task_id"] in json.dumps(value)
                     else "RETAINED_SCOPED_MEMORY"}
    projection = {"schema": "minitz.current_projection/v1", "authority": "DERIVATIVE_CURRENT_PROJECTION",
        "task": tasks.task_context_payload(tasks.task_by_id(program, current["task_id"])),
        "source": tasks.program_identity(program), "retained_memory_refs": attachments}
    projection_path = STATE / "current-task-projection.json"
    projection_path.write_text(json.dumps(projection, sort_keys=True) + "\n")
    projection_path.chmod(0o600)
    attachments["canonical-current-projection"] = {"path": str(projection_path),
        "sha256": hashlib.sha256(projection_path.read_bytes()).hexdigest(), "scope": "CURRENT_TASK"}
    payload = {"schema": "minitz.sandbox_foundation/v1", "authority": "EVIDENCE_ONLY", "state": "STARTING",
        "task": current, "program": tasks.program_identity(program), "attachments": attachments,
        "os_release": Path("/etc/os-release").read_text(), "task_progression_mutated": False,
        "writer_state": "NOT_STARTED", "host_os_mutation": False, "started_at_epoch": time.time()}
    resource_mode = os.environ.get("MINITZ_LOCAL_AI_MODE", "owned")
    payload["local_resource_mode"] = resource_mode
    payload["model_execution_location"] = "existing host resource" if resource_mode == "resident-resource" else "sandbox"
    persist(payload)
    with (STATE / "ollama.log").open("a") as log:
        server = None if resource_mode == "resident-resource" else subprocess.Popen(["/usr/local/bin/ollama", "serve"], stdout=log, stderr=subprocess.STDOUT)
        stopped = threading.Event()
        coder, control, production_child = None, None, None
        def shutdown(signum, frame):
            stopped.set()
            if production_child is not None and production_child.poll() is None:
                # Explicit OFF drains at the existing task boundary; never kill a turn.
                pause=Path(os.environ["BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT"])/"customer-pause-request.json"
                try:
                    with pause.open("x") as stream:
                        json.dump({"reason":"MINITZ_SANDBOX_OFF", "maintenance_owned":True},stream)
                except FileExistsError:
                    pass
                return  # Main wait owns reaping; signal handlers must not block.
            if coder is not None:
                coder.close()
            if control is not None:
                control.shutdown()
                control.server_close()
            if server is not None:
                server.terminate()
        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        try:
            for _ in range(60):
                if server is not None and server.poll() is not None:
                    raise RuntimeError("Local runtime exited before API readiness")
                try:
                    get_json("/api/tags")
                    break
                except (OSError, ValueError):
                    time.sleep(0.5)
            else:
                raise RuntimeError("Local runtime API unavailable")
            payload["qualification"] = qualify(program)
            passed = all(result.get("quality", {}).get("verdict") == "PASS" for result in payload["qualification"]["results"])
            payload["state"] = ("LOCAL_CAPABILITY_QUALIFIED" if payload["qualification"]["current_capacity"]["allowed"]
                                else "LOCAL_CAPABILITY_QUALIFIED_CAPACITY_DEGRADED") if passed else "NEEDS_ATTENTION"
        except Exception as exc:
            payload.update(state="NEEDS_ATTENTION", failure=type(exc).__name__ + ": " + str(exc))
        # Local-model qualification affects that route, not the whole product.
        try:
            control, payload["control"] = startup_attachments.attach_control(payload)
            payload["control_attached_at_epoch"] = time.time()
            coder_log = (STATE / "coder.log").open("a")
            coder = startup_attachments.CoderTransport(Path(os.environ.get("BIELLA_CODEX_BIN", "/resources/codex")), STATE / "codex", coder_log)
            payload["coder"] = startup_attachments.qualify_coder_protocol(coder.rpc, coder.notify)
            payload["coder_attached_at_epoch"] = time.time()
            if payload["coder"]["state"] not in {"PROTOCOL_AUTH_ATTACHED", "PROTOCOL_LOCAL_READY"}:
                raise RuntimeError("Coder credential reference not attached")
            payload["state"] = "STARTUP_ATTACHMENTS_PASSED"
            payload["writer_state"] = "CODER_ATTACHED_NO_TURN_BEFORE_STARTUP_ACCEPTANCE"
        except Exception as exc:
            payload.update(state="NEEDS_ATTENTION", attachment_failure=type(exc).__name__ + ": " + str(exc))
        if os.environ.get("MINITZ_PRODUCTION_AUTORUN") == "1":
            try:
                spec=importlib.util.spec_from_file_location("minitz_production_handoff",Path(__file__).with_name("production.py"))
                handoff=importlib.util.module_from_spec(spec)
                spec.loader.exec_module(handoff)
                runtime=Path(os.environ["BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT"])
                pause=runtime/"customer-pause-request.json"
                if pause.is_file():
                    request=json.loads(pause.read_text())
                    if request.get("maintenance_owned") is True and request.get("reason")=="MINITZ_SANDBOX_OFF":
                        pause.unlink()
                production_log=(STATE/"production.log").open("a")
                production_child,payload["production"]=handoff.launch_production(
                    Path(os.environ["MINITZ_DEVELOPMENT_ROOT"]),runtime,production_log)
                payload["writer_state"]="CANONICAL_EXECUTOR_"+payload["production"]["state"]
            except Exception as exc:
                payload["production"]={"state":"LAUNCH_FAILED","failure":type(exc).__name__+": "+str(exc)}
        payload["observed_at_epoch"] = time.time()
        persist(payload)
        print(json.dumps({"state": payload["state"], "evidence": str(EVIDENCE), "task_id": current["task_id"]}), flush=True)
        if production_child is not None:
            code=production_child.wait()
            payload["production"].update(state="EXITED",returncode=code)
            payload["observed_at_epoch"]=time.time()
            persist(payload)
            if stopped.is_set():
                shutdown(None,None)
                return 0
        if server is not None:
            return server.wait()
        stopped.wait()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
