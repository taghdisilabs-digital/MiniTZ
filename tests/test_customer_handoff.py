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
sys.path.insert(0, str(LOCAL_AI))
MODULE = LOCAL_AI / "biella_customer_handoff.py"
spec = importlib.util.spec_from_file_location("biella_customer_handoff", MODULE)
assert spec and spec.loader
handoff = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = handoff
spec.loader.exec_module(handoff)


def _git_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    return repo


def _runtime(root: Path) -> Path:
    runtime = root / "runtime"
    (runtime / "task-memory").mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    (runtime / "runtime.json").write_text(json.dumps({"task_id": "D03-01", "child_pid": None}) + "\n")
    (runtime / "task-memory/D03-01.json").write_text('{"task_id":"D03-01","session_id":null}\n')
    (runtime / "memory/current-task.json").write_text('{"task_id":"D03-01","task_memory":{"session_id":null}}\n')
    return runtime


def test_checkpoint_preserves_dirty_bytes_and_records_exact_identity(tmp_path: Path, monkeypatch):
    repo = _git_repo(tmp_path)
    runtime = _runtime(tmp_path)
    dirty = repo / "tracked.txt"
    dirty.write_text("preserved progress\n", encoding="utf-8")
    before = hashlib.sha256(dirty.read_bytes()).hexdigest()
    manager = handoff.BiellaCustomerHandoff(repo, runtime, tmp_path / "handoff")
    monkeypatch.setattr(manager, "service_states", lambda: {
        name: {"active": False, "enabled": "disabled"} for name in handoff.PROTECTED_SERVICES
    })
    monkeypatch.setattr(manager, "sleep_services", lambda: None)
    checkpoint = manager.checkpoint()
    assert hashlib.sha256(dirty.read_bytes()).hexdigest() == before
    assert checkpoint["repo"]["head"] == subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    assert checkpoint["workspace_fingerprint"] == handoff.dirty_workspace_fingerprint(repo)
    assert checkpoint["task_id"] == "D03-01"
    assert checkpoint["runtime"]["task_memory_sha256"]
    assert checkpoint["runtime"]["projection_sha256"]


def test_resume_refuses_while_any_customer_container_is_running(tmp_path: Path, monkeypatch):
    repo = _git_repo(tmp_path)
    runtime = _runtime(tmp_path)
    manager = handoff.BiellaCustomerHandoff(repo, runtime, tmp_path / "handoff")
    monkeypatch.setattr(manager, "service_states", lambda: {
        name: {"active": False, "enabled": "disabled"} for name in handoff.PROTECTED_SERVICES
    })
    monkeypatch.setattr(manager, "sleep_services", lambda: None)
    manager.checkpoint()
    monkeypatch.setattr(manager, "running_customer_count", lambda: 1)
    with pytest.raises(handoff.HandoffError, match="customer container"):
        manager.resume()


def test_resume_restores_exact_pre_customer_service_state(tmp_path: Path, monkeypatch):
    repo = _git_repo(tmp_path)
    runtime = _runtime(tmp_path)
    manager = handoff.BiellaCustomerHandoff(repo, runtime, tmp_path / "handoff")
    desired = {
        "biella-codex-production.service": {"active": True, "enabled": "enabled"},
        "biella-ollama.service": {"active": True, "enabled": "enabled"},
        "biella-qwen-residency.service": {"active": False, "enabled": "disabled"},
    }
    monkeypatch.setattr(manager, "service_states", lambda: desired)
    monkeypatch.setattr(manager, "cooperative_pause", lambda timeout_seconds=3600.0: None)
    monkeypatch.setattr(manager, "sleep_services", lambda: None)
    manager.checkpoint()
    monkeypatch.setattr(manager, "running_customer_count", lambda: 0)
    monkeypatch.setattr(manager, "verify_source_alignment", lambda: None)
    enabled, active = [], []
    monkeypatch.setattr(manager, "set_enabled_state", lambda name, state: enabled.append((name, state)))
    monkeypatch.setattr(manager, "set_active_state", lambda name, state: active.append((name, state)))
    result = manager.resume()
    assert result["status"] == "RESTORED"
    assert enabled == [(name, desired[name]["enabled"]) for name in handoff.PROTECTED_SERVICES]
    assert active == [(name, desired[name]["active"]) for name in handoff.PROTECTED_SERVICES]
    assert not manager.active_checkpoint_path.exists()


def test_import_lessons_accepts_only_project_neutral_sanitized_records(tmp_path: Path):
    repo = _git_repo(tmp_path)
    runtime = _runtime(tmp_path)
    manager = handoff.BiellaCustomerHandoff(repo, runtime, tmp_path / "handoff")
    source = tmp_path / "lessons.json"
    source.write_text(json.dumps({
        "schema": "project_sandbox.sanitized_lessons/v1",
        "lessons": [{
            "category": "failure_fix", "title": "Module mode repair",
            "problem": "A runtime rejected an import because module mode differed from emitted output.",
            "method": "Align module mode with emitted output and rerun the same deterministic runtime check.",
            "result": "The build and runtime check passed.", "evidence_type": "test",
            "timestamp": "2026-09-07T18:00:00+00:00",
        }],
    }) + "\n")
    inbox = tmp_path / "inbox"
    result = manager.import_lessons(source, inbox)
    assert result["status"] == "IMPORTED"
    imported = json.loads(Path(result["path"]).read_text())
    assert imported["schema"] == "biella.external_lesson_candidate/v1"
    assert imported["lessons"][0]["title"] == "Module mode repair"


def test_import_lessons_rejects_url_path_or_project_identity(tmp_path: Path):
    repo = _git_repo(tmp_path); runtime = _runtime(tmp_path)
    manager = handoff.BiellaCustomerHandoff(repo, runtime, tmp_path / "handoff")
    source = tmp_path / "lessons.json"
    source.write_text(json.dumps({"schema":"project_sandbox.sanitized_lessons/v1","lessons":[{
        "category":"failure_fix","title":"customer repo repair","problem":"Read https://example.test/repo",
        "method":"Use /srv/project-sandboxes/site-a/workspace","result":"passed",
        "evidence_type":"test","timestamp":"2026-09-07T18:00:00+00:00"}]}) + "\n")
    with pytest.raises(handoff.HandoffError, match="project-neutral"):
        manager.import_lessons(source, tmp_path / "inbox")


def test_handoff_systemd_unit_exposes_only_fixed_root_owned_action():
    unit = (LOCAL_AI / "biella-customer-handoff@.service").read_text(encoding="utf-8")
    assert "Type=oneshot" in unit
    assert "RequiresMountsFor=/mnt/biella-extra" in unit
    assert "ExecStart=/usr/local/lib/biella-ai/biella_customer_handoff.py %i" in unit
    assert "TimeoutStartSec=3700" in unit


def test_handoff_cli_accepts_only_checkpoint_resume_import_and_status():
    choices = handoff._parser()._subparsers._group_actions[0].choices
    assert set(choices) == {"checkpoint", "resume", "import-lessons", "status", "guard-production"}


def test_installer_deploys_customer_handoff_helper_and_unit():
    installer = (LOCAL_AI / "install-biella-ai.sh").read_text(encoding="utf-8")
    assert '"$SOURCE_DIR/biella_customer_handoff.py"' in installer
    assert '"$SOURCE_DIR/biella-customer-handoff@.service"' in installer
    assert '/etc/systemd/system/biella-customer-handoff@.service' in installer


def test_guard_production_refuses_running_customer(tmp_path: Path, monkeypatch):
    repo = _git_repo(tmp_path); runtime = _runtime(tmp_path)
    manager = handoff.BiellaCustomerHandoff(repo, runtime, tmp_path / "handoff")
    monkeypatch.setattr(manager, "running_customer_count", lambda: 1)
    with pytest.raises(handoff.HandoffError, match="customer container"):
        manager.guard_production()
    monkeypatch.setattr(manager, "running_customer_count", lambda: 0)
    manager.guard_production()


def test_production_unit_blocks_start_while_customers_run():
    unit = (LOCAL_AI / "biella-codex-production.service").read_text(encoding="utf-8")
    assert "After=network-online.target docker.service project-sandbox-broker.service" in unit
    assert "ExecCondition=/usr/local/lib/biella-ai/biella_customer_handoff.py guard-production" in unit


def test_workstation_installer_preserves_existing_ai_service_enablement():
    installer = (ROOT / "ops/workstation/install-biella-workstation.sh").read_text(encoding="utf-8")
    assert "ollama_enablement" in installer
    assert "qwen_enablement" in installer
    assert 'if [[ "$ollama_enablement" == "enabled" ]]' in installer
    assert 'if [[ "$qwen_enablement" == "enabled" ]]' in installer
