from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
MODULE = LOCAL_AI / "minitz_lifecycle.py"


def _load():
    spec = importlib.util.spec_from_file_location("minitz_lifecycle", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_sleep_freezes_writer_but_keeps_model_residency_warm(monkeypatch):
    lifecycle = _load()
    calls = []
    monkeypatch.setattr(lifecycle, "_systemctl", lambda *args: calls.append(args))
    lifecycle.sleep()
    assert ("stop", "minitz-on.target") in calls
    assert ("stop", "minitz-production.service") in calls
    assert ("disable", "minitz-production.service") in calls
    for service in lifecycle.MODEL_SERVICES:
        assert ("stop", service) not in calls
        assert ("disable", service) not in calls


def test_off_deep_stops_all_minitz_runtime_services(monkeypatch):
    lifecycle = _load()
    calls = []
    monkeypatch.setattr(lifecycle, "_systemctl", lambda *args: calls.append(args))
    lifecycle.off()
    assert calls[0] == ("stop", "minitz-on.target")
    for service in lifecycle.OFF_SERVICES:
        assert ("stop", service) in calls
        assert ("disable", service) in calls


def test_owner_on_starts_services_without_off_receipt(monkeypatch):
    lifecycle = _load()
    calls = []
    monkeypatch.setattr(lifecycle, "_systemctl", lambda *args: calls.append(args))
    lifecycle.on()
    assert calls[0] == ("enable", "minitz-ollama.service")
    starts = [call[1] for call in calls if len(call) == 2 and call[0] == "start"]
    assert starts[-1] == "minitz-on.target"
    assert starts.index("minitz-production.service") > starts.index("minitz-qwen-residency.service")
    assert starts.index("minitz-production.service") > starts.index("minitz-control-gateway.service")


def test_owner_entrypoints_use_canonical_lifecycle_controller():
    expected = {
        "minitz-owner-sleep": "minitz_lifecycle.py sleep",
        "minitz-owner-off": "minitz_lifecycle.py off",
        "minitz-owner-on": "minitz_lifecycle.py on",
    }
    for name, command in expected.items():
        text = (LOCAL_AI / name).read_text(encoding="utf-8")
        assert command in text
        assert "minitz_customer_handoff.py checkpoint" not in text


def _git_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    (repo / "source.txt").write_text("ready\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    return repo


def test_qualification_receipt_binds_exact_clean_source_and_task_program(tmp_path, monkeypatch):
    lifecycle = _load()
    repo = _git_repo(tmp_path)
    program = tmp_path / "TASK_PROGRAM.json"
    program.write_text(json.dumps({"revision": 7, "tasks": []}, sort_keys=True) + "\n", encoding="utf-8")
    receipt = tmp_path / "READY_TO_ON.json"
    calls = []
    monkeypatch.setattr(lifecycle, "_unit_active", lambda _unit: False)
    monkeypatch.setattr(lifecycle, "_qualification_command", lambda args, cwd: calls.append((tuple(args), cwd)) or None)
    monkeypatch.setattr(lifecycle, "_failed_systemd_units", lambda: [])
    result = lifecycle.qualify(repo_root=repo, task_program_path=program, receipt_path=receipt)
    assert result["schema"] == "minitz.on_readiness/v1"
    assert result["repo_head"] == subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    assert result["task_program_sha256"]
    assert result["qualified_while_off"] is True
    assert len(calls) == 6
    assert tuple(calls[2][0][-len(lifecycle.TASK_VALIDATION_TESTS):]) == lifecycle.TASK_VALIDATION_TESTS
    assert calls[3][0] == ("bash", "tests/local_ai_runtime_smoke_test.sh")
    assert calls[4][0] == ("bash", "tests/workstation_supervisor_contract_test.sh")
    assert calls[5][0] == ("bash", "tests/control_gateway_service_contract_test.sh")
    assert lifecycle.assert_ready(repo_root=repo, task_program_path=program, receipt_path=receipt)["status"] == "READY"


def test_qualification_is_allowed_while_owner_on_is_active(tmp_path, monkeypatch):
    lifecycle = _load()
    repo = _git_repo(tmp_path)
    program = tmp_path / "TASK_PROGRAM.json"
    program.write_text('{"revision":1,"tasks":[]}\n', encoding="utf-8")
    receipt = tmp_path / "READY_TO_ON.json"
    monkeypatch.setattr(lifecycle, "_unit_active", lambda _unit: True)
    monkeypatch.setattr(lifecycle, "_qualification_command", lambda args, cwd: None)
    monkeypatch.setattr(lifecycle, "_failed_systemd_units", lambda: [])
    result = lifecycle.qualify(repo_root=repo, task_program_path=program, receipt_path=receipt)
    assert result["qualified_while_off"] is False
    assert lifecycle.assert_ready(repo_root=repo, task_program_path=program, receipt_path=receipt)["status"] == "READY"


def test_readiness_rejects_dirty_or_stale_source(tmp_path, monkeypatch):
    lifecycle = _load()
    repo = _git_repo(tmp_path)
    program = tmp_path / "TASK_PROGRAM.json"
    program.write_text('{"revision":1,"tasks":[]}\n', encoding="utf-8")
    receipt = tmp_path / "READY_TO_ON.json"
    monkeypatch.setattr(lifecycle, "_unit_active", lambda _unit: False)
    monkeypatch.setattr(lifecycle, "_qualification_command", lambda args, cwd: None)
    monkeypatch.setattr(lifecycle, "_failed_systemd_units", lambda: [])
    lifecycle.qualify(repo_root=repo, task_program_path=program, receipt_path=receipt)
    (repo / "source.txt").write_text("changed\n", encoding="utf-8")
    with pytest.raises(lifecycle.LifecycleError, match="workspace is dirty"):
        lifecycle.assert_ready(repo_root=repo, task_program_path=program, receipt_path=receipt)


def test_readiness_rejects_task_program_change_even_when_target_is_active(tmp_path, monkeypatch):
    lifecycle = _load()
    repo = _git_repo(tmp_path)
    program = tmp_path / "TASK_PROGRAM.json"
    program.write_text('{"revision":1,"tasks":[]}\n', encoding="utf-8")
    receipt = tmp_path / "READY_TO_ON.json"
    monkeypatch.setattr(lifecycle, "_unit_active", lambda _unit: False)
    monkeypatch.setattr(lifecycle, "_qualification_command", lambda args, cwd: None)
    monkeypatch.setattr(lifecycle, "_failed_systemd_units", lambda: [])
    lifecycle.qualify(repo_root=repo, task_program_path=program, receipt_path=receipt)
    program.write_text('{"revision":2,"tasks":[]}\n', encoding="utf-8")
    monkeypatch.setattr(lifecycle, "_unit_active", lambda _unit: True)
    with pytest.raises(lifecycle.LifecycleError, match="Task Program changed"):
        lifecycle.assert_ready(repo_root=repo, task_program_path=program, receipt_path=receipt)


def test_startup_attachment_check_does_not_require_off_receipt(tmp_path, monkeypatch):
    lifecycle = _load()
    program = tmp_path / "TASK_PROGRAM.json"
    program.write_text('{"revision":1,"tasks":[]}\n', encoding="utf-8")
    monkeypatch.setattr(lifecycle, "ATTACHMENT_PATHS", (program,))
    monkeypatch.setattr(lifecycle, "_unit_active", lambda _unit: True)
    result = lifecycle.assert_startup_attached(task_program_path=program)
    assert result["status"] == "ATTACHED"
    assert result["task_program_sha256"]


def test_production_writer_has_startup_attachment_gate_and_target_is_canonical():
    unit = (LOCAL_AI / "minitz-production.service").read_text(encoding="utf-8")
    target = (LOCAL_AI / "minitz-on.target").read_text(encoding="utf-8")
    assert "ExecStartPre=/usr/local/lib/minitz-ai/minitz_lifecycle.py assert-startup-attached" in unit
    assert "Wants=network-online.target docker.service" in target
    assert "minitz-production.service" in target
    assert "minitz-control-gateway.service" in target
    assert "project-sandbox-broker.service" in target


@pytest.mark.parametrize("contents", [None, "{", "[]"])
def test_startup_gate_rejects_missing_or_invalid_task_program(tmp_path, monkeypatch, contents):
    lifecycle = _load()
    program = tmp_path / "TASK_PROGRAM.json"
    if contents is not None:
        program.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(lifecycle, "ATTACHMENT_PATHS", ())
    monkeypatch.setattr(lifecycle, "_unit_active", lambda _unit: True)
    with pytest.raises(lifecycle.LifecycleError, match="Task Program"):
        lifecycle.assert_startup_attached(task_program_path=program)


@pytest.mark.parametrize("missing_index", [0, 1])
def test_startup_gate_rejects_each_missing_memory_attachment(tmp_path, monkeypatch, missing_index):
    lifecycle = _load()
    program = tmp_path / "TASK_PROGRAM.json"
    program.write_text('{"revision":1,"tasks":[]}\n', encoding="utf-8")
    attachments = tuple(tmp_path / path.name for path in lifecycle.ATTACHMENT_PATHS)
    for index, attachment in enumerate(attachments):
        if index != missing_index:
            attachment.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(lifecycle, "ATTACHMENT_PATHS", attachments)
    monkeypatch.setattr(lifecycle, "_unit_active", lambda _unit: True)
    with pytest.raises(lifecycle.LifecycleError, match="attachments"):
        lifecycle.assert_startup_attached(task_program_path=program)


@pytest.mark.parametrize("unavailable", [
    "minitz-ollama.service",
    "minitz-qwen-residency.service",
    "project-sandbox-broker.service",
    "minitz-control-gateway.service",
])
def test_startup_gate_rejects_each_unavailable_prerequisite(tmp_path, monkeypatch, unavailable):
    lifecycle = _load()
    program = tmp_path / "TASK_PROGRAM.json"
    program.write_text('{"revision":1,"tasks":[]}\n', encoding="utf-8")
    monkeypatch.setattr(lifecycle, "ATTACHMENT_PATHS", (program,))
    monkeypatch.setattr(lifecycle, "_unit_active", lambda unit: unit != unavailable)
    with pytest.raises(lifecycle.LifecycleError, match=unavailable):
        lifecycle.assert_startup_attached(task_program_path=program)


def test_installer_deploys_lifecycle_controller_entrypoints_and_target():
    installer = (LOCAL_AI / "install-minitz-ai.sh").read_text(encoding="utf-8")
    for marker in (
        '"$SOURCE_DIR/minitz_lifecycle.py"',
        '"$SOURCE_DIR/minitz-owner-on"',
        '"$SOURCE_DIR/minitz-owner-off"',
        '"$SOURCE_DIR/minitz-owner-sleep"',
        '"$SOURCE_DIR/minitz-on.target"',
        "/etc/systemd/system/minitz-on.target",
        "/usr/local/bin/minitz-owner-on",
        "/usr/local/bin/minitz-owner-off",
        "/usr/local/bin/minitz-owner-sleep",
    ):
        assert marker in installer


def test_default_readiness_repo_is_the_ubuntu_2604_target_sandbox():
    lifecycle = _load()
    assert lifecycle.DEFAULT_REPO_ROOT == Path(
        "/root/attached-storage/minitz-os-sandbox/workspace/repo"
    )
    assert lifecycle.DEFAULT_REPO_ROOT != Path("/root/minitz/repos/minitz-engine")


def test_owner_on_is_not_blocked_by_off_receipt(monkeypatch):
    lifecycle = _load()
    calls = []
    def old_gate():
        raise lifecycle.LifecycleError("OFF receipt is missing")
    monkeypatch.setattr(lifecycle, "assert_ready", old_gate)
    monkeypatch.setattr(lifecycle, "_systemctl", lambda *args: calls.append(args))
    result = lifecycle.on()
    assert result["state"] == "ON"
    assert ("start", "minitz-production.service") in calls
