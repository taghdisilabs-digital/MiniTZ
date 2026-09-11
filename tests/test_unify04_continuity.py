from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(LOCAL_AI))

import biella_memory_compactor as compactor
import biella_production_runner as runner
import biella_production_state as state
import biella_task_packet as packets
import minitz_task_program as minitz

_HANDOFF_MODULE = LOCAL_AI / "biella_customer_handoff.py"
_HANDOFF_SPEC = importlib.util.spec_from_file_location("unify04_customer_handoff", _HANDOFF_MODULE)
assert _HANDOFF_SPEC and _HANDOFF_SPEC.loader
handoff = importlib.util.module_from_spec(_HANDOFF_SPEC)
sys.modules[_HANDOFF_SPEC.name] = handoff
_HANDOFF_SPEC.loader.exec_module(handoff)

PROGRAM_PATH = ROOT.parent.parent / "analysis/live_audit/TASK_PROGRAM.json"
TASK_ID = "UNIFY-04"
SESSION_ID = "unify04-test-session"


def _current_task() -> tuple[dict[str, object], state.TaskRecord, dict[str, object]]:
    program = minitz.load(PROGRAM_PATH)
    row = minitz.task_by_id(program, TASK_ID)
    authority = {
        "task_id": TASK_ID,
        "task_revision": int(row["revision"]),
        "task_digest": str(row["task_record_sha256"]),
        "scope_ref": f"task://minitz/{TASK_ID}/{row['revision']}",
        "progression_authority": "MINITZ_TASK_PROGRAM_ONLY",
    }
    task = state.TaskRecord(
        TASK_ID,
        minitz.task_class(program, row),
        str(row["title"]),
        str(row["status"]),
        tuple(str(item) for item in row.get("completion", {}).get("evidence", ()))
        + (f"MINITZ_TASK_REVISION:{row['revision']}", f"MINITZ_TASK_SHA256:{row['task_record_sha256']}"),
        "minitz",
    )
    return program, task, authority


def _git_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "MiniTZ test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "minitz@example.invalid"], check=True)
    (repo / "task-owned.txt").write_text("task-owned bytes\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "task-owned.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
    return repo


def _minitz_runtime(root: Path, repo: Path, authority: dict[str, object]) -> Path:
    runtime = root / "runtime"
    (runtime / "task-memory").mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    owned = repo / "task-owned.txt"
    task_memory = {
        "schema": "biella.task_memory/v1",
        "task_id": TASK_ID,
        "session_id": SESSION_ID,
        "project_root": str(repo),
        "task_identity": authority,
        "owned_files": {
            "task-owned.txt": hashlib.sha256(owned.read_bytes()).hexdigest(),
        },
    }
    (runtime / "runtime.json").write_text(json.dumps({
        "schema": "biella.runtime/v1",
        "task_id": TASK_ID,
        "task_session_id": SESSION_ID,
        "session_task_id": TASK_ID,
        "status": "RUNNING",
    }, sort_keys=True) + "\n", encoding="utf-8")
    (runtime / "task-memory" / f"{TASK_ID}.json").write_text(
        json.dumps(task_memory, sort_keys=True) + "\n", encoding="utf-8"
    )
    (runtime / "memory/current-task.json").write_text(json.dumps({
        "schema": "biella.compacted_task_projection/v1",
        "task_id": TASK_ID,
        "task_identity": authority,
        "session_identity": {"task_id": TASK_ID, "session_id": SESSION_ID},
    }, sort_keys=True) + "\n", encoding="utf-8")
    return runtime


def _inactive_services() -> dict[str, dict[str, object]]:
    return {name: {"active": False, "enabled": "disabled"} for name in handoff.PROTECTED_SERVICES}


def _wake_receipt(runtime: Path, program_identity: dict[str, object], authority: dict[str, object]) -> None:
    path = runtime / "recovery/owner-os-wake-current.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "minitz.owner_wake_receipt/v1",
        "current_task_id": TASK_ID,
        "current_task_revision": authority["task_revision"],
        "current_task_sha256": authority["task_digest"],
        "program_revision": program_identity["revision"],
        "program_sha256": program_identity["sha256"],
        "owner_instruction": "EXPLICIT_TEST_RESUME",
        "host_power_change_authorized": False,
        "control_gateway_authorized": False,
    }, sort_keys=True) + "\n", encoding="utf-8")


def test_current_task_identity_is_bound_to_packets_capsules_and_projection():
    program, task, authority = _current_task()
    program_identity = minitz.program_identity(program)
    continuity = runner._minitz_capsule_continuity(ROOT, Path("/tmp/unify04-no-runtime"), task)
    capsule = packets.build_task_memory_capsule(
        task,
        ROOT,
        session_id=SESSION_ID,
        summary="api_key=TEST_ONLY_VALUE",
        evidence=("authorization=TEST_ONLY_VALUE",),
        task_revision=int(authority["task_revision"]),
        task_digest=str(authority["task_digest"]),
        program_identity=program_identity,
        worktree_identity=continuity["worktree_identity"],
        owner_lifecycle=continuity["owner_lifecycle"],
        policy_ref="ops/workstation/AGENTS.md",
    )
    encoded = json.dumps(capsule, sort_keys=True)
    assert capsule["task_revision"] == authority["task_revision"]
    assert capsule["task_digest"] == authority["task_digest"]
    assert capsule["scope_ref"] == authority["scope_ref"]
    assert capsule["progression_authority"] == "MINITZ_TASK_PROGRAM_ONLY"
    assert capsule["bootstrap"]["source"] == "CURRENT_MINITZ_OS_POLICY_AND_DURABLE_TASK_MEMORY"
    assert capsule["bootstrap"]["provider_session_override"] is False
    assert "TEST_ONLY_VALUE" not in encoded

    production = state.ProductionState(
        ROOT, "IN_PROGRESS", "minitz", TASK_ID, [],
        run_id="minitz-task-program", priority_policy="MINITZ_TASK_PROGRAM",
    )
    task_packet = packets.compile_task_packet(ROOT, production, task)
    resume_packet = packets.compile_resume_packet(task, Path("/tmp/unify04-capsule.json"))
    for packet in (task_packet, resume_packet):
        packet_lower = packet.lower()
        assert f"MINITZ_TASK_REVISION: {authority['task_revision']}" in packet
        assert f"MINITZ_TASK_SHA256: {authority['task_digest']}" in packet
        assert "provider/model/helper changes" in packet_lower
        assert "another" in packet_lower and "progression" in packet_lower

    projection = compactor._projection(
        {"content": {}, "categories": {}, "task_classes": {}, "policy": {}, "records": [],
         "sources": [], "capabilities": {}, "data_residency": {}},
        current_task_id=TASK_ID,
        task_memory={**capsule, "unrelated_payload": "x" * 20000},
        failures=[],
        maximum_chars=700,
    )
    retained = projection["task_memory"]
    assert retained["task_identity"] == authority
    assert retained["session_identity"]["session_id"] == SESSION_ID
    assert retained["program_identity"] == program_identity
    assert retained["bootstrap"]["owner_resume_required"] is True
    assert "unrelated_payload" not in retained


def test_checkpoint_preserves_identity_through_owner_sleep_management_change_and_explicit_resume(tmp_path: Path, monkeypatch):
    program, _task, authority = _current_task()
    repo = _git_repo(tmp_path)
    runtime = _minitz_runtime(tmp_path, repo, authority)
    manager = handoff.BiellaCustomerHandoff(repo, runtime, tmp_path / "handoff")
    monkeypatch.setattr(manager, "service_states", _inactive_services)
    monkeypatch.setattr(manager, "sleep_services", lambda: None)
    checkpoint = manager.checkpoint()

    assert checkpoint["task_id"] == TASK_ID
    assert checkpoint["task_identity"]["task_digest"] == authority["task_digest"]
    assert checkpoint["session_identity"]["session_id"] == SESSION_ID
    assert checkpoint["owner_lifecycle"]["state"] == "OWNER_SLEEP"
    assert checkpoint["task_scope"]["owned_files"]["task-owned.txt"]

    first = manager.resume()
    assert first["status"] == "OWNER_SLEEP_PRESERVED"
    assert manager.active_checkpoint_path.is_file()

    (repo / "management-change.txt").write_text("non-overlapping management change\n", encoding="utf-8")
    second = manager.resume()
    assert second["status"] == "OWNER_SLEEP_PRESERVED"
    assert manager.active_checkpoint_path.is_file()

    program_identity = minitz.program_identity(program)
    _wake_receipt(runtime, program_identity, authority)
    monkeypatch.setattr(manager, "running_customer_count", lambda: 0)
    monkeypatch.setattr(manager, "verify_source_alignment", lambda: None)
    monkeypatch.setattr(manager, "set_enabled_state", lambda *_args: None)
    monkeypatch.setattr(manager, "set_active_state", lambda *_args: None)
    restored = manager.resume()
    assert restored["status"] == "RESTORED"
    assert restored["checkpoint_sha256"]
    assert not manager.active_checkpoint_path.exists()


def test_checkpoint_conflicting_overlap_fails_closed_with_exact_observed_identity(tmp_path: Path, monkeypatch):
    _program, _task, authority = _current_task()
    repo = _git_repo(tmp_path)
    runtime = _minitz_runtime(tmp_path, repo, authority)
    manager = handoff.BiellaCustomerHandoff(repo, runtime, tmp_path / "handoff")
    monkeypatch.setattr(manager, "service_states", _inactive_services)
    monkeypatch.setattr(manager, "sleep_services", lambda: None)
    checkpoint = manager.checkpoint()
    expected = checkpoint["task_scope"]["owned_files"]["task-owned.txt"]
    (repo / "task-owned.txt").write_text("conflicting overlap\n", encoding="utf-8")
    observed = hashlib.sha256((repo / "task-owned.txt").read_bytes()).hexdigest()

    with pytest.raises(handoff.HandoffError, match="task-owned checkpoint overlap changed") as error:
        manager.resume()
    message = str(error.value)
    assert f"task-owned.txt (expected={expected}, observed={observed})" in message
    assert manager.active_checkpoint_path.is_file()


def test_checkpoint_rejects_foreign_owner_stale_binding_and_raw_secret_payload(tmp_path: Path, monkeypatch):
    _program, _task, authority = _current_task()
    repo = _git_repo(tmp_path)
    runtime = _minitz_runtime(tmp_path, repo, authority)
    manager = handoff.BiellaCustomerHandoff(repo, runtime, tmp_path / "handoff")
    monkeypatch.setattr(manager, "service_states", _inactive_services)
    monkeypatch.setattr(manager, "sleep_services", lambda: None)
    manager.checkpoint()

    payload = json.loads(manager.active_checkpoint_path.read_text(encoding="utf-8"))
    payload["owner_id"] = "foreign-owner"
    manager.active_checkpoint_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(handoff.HandoffError, match="checkpoint owner is foreign"):
        manager.resume()

    payload.pop("owner_id")
    manager.active_checkpoint_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(handoff.HandoffError, match="missing or foreign"):
        manager.resume()

    payload["owner_id"] = handoff.HANDOFF_OWNER_ID
    payload["task_identity"] = {**payload["task_identity"], "task_digest": "0" * 64}
    manager.active_checkpoint_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(handoff.HandoffError, match="not bound to runtime identity"):
        manager.resume()

    payload["task_identity"] = json.loads(manager.active_checkpoint_path.read_text(encoding="utf-8"))["runtime"]["task_identity"]
    payload["api_key"] = "TEST_ONLY_VALUE"
    manager.active_checkpoint_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(handoff.HandoffError, match="raw credential"):
        manager.resume()


def test_handoff_identity_uses_first_active_task_row_without_persisted_current_execution(tmp_path: Path, monkeypatch):
    task = {
        "task_id": "BRIDGE-TEST",
        "revision": 2,
        "status": "WORKING",
        "active_task_survival": True,
        "review_state": "VALUE_GATE_PASSED",
        "title": "Bridge test",
        "dependencies": [],
        "write_scope": {"authority": "TASK_OWNED_ONLY", "execution_root": str(tmp_path), "allowed_paths": [str(tmp_path)]},
        "workers": [{"worker_id": "chatgpt:test", "role": "PRIMARY_WRITER", "write_authority": True, "status": "WORKING"}],
    }
    task["worker_state_sha256"] = minitz.digest(task["workers"])
    task["task_record_sha256"] = minitz.task_digest(task)
    program_path = tmp_path / "TASK_PROGRAM.json"
    program = {
        "schema": "minitz.living_task_program/v1",
        "program_id": "MINITZ_REBORN_SINGLE_TASK_PROGRAM",
        "revision": 9,
        "tasks": [task],
    }
    program_path.write_text(json.dumps(program, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setenv("MINITZ_TASK_PROGRAM_PATH", str(program_path))
    identity = handoff._minitz_program_identity("BRIDGE-TEST")
    assert identity is not None
    assert identity["task_id"] == "BRIDGE-TEST"
    assert identity["task_revision"] == 2
    assert identity["task_digest"] == task["task_record_sha256"]
    assert identity["program_sha256"] == hashlib.sha256(program_path.read_bytes()).hexdigest()
