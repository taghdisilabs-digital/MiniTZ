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
    assert ("stop", "biella-codex-production.service") in calls
    assert ("disable", "biella-codex-production.service") in calls
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


def test_on_requires_fresh_readiness_before_starting_any_service(monkeypatch):
    lifecycle = _load()
    calls = []
    monkeypatch.setattr(lifecycle, "assert_ready", lambda: calls.append(("READY",)))
    monkeypatch.setattr(lifecycle, "_systemctl", lambda *args: calls.append(args))
    lifecycle.on()
    assert calls[0] == ("READY",)
    starts = [call[1] for call in calls if len(call) == 2 and call[0] == "start"]
    assert starts[-1] == "minitz-on.target"
    assert starts.index("biella-codex-production.service") > starts.index("biella-qwen-residency.service")
    assert starts.index("biella-codex-production.service") > starts.index("biella-control-gateway.service")


def test_owner_entrypoints_use_canonical_lifecycle_controller():
    expected = {
        "minitz-owner-sleep": "minitz_lifecycle.py sleep",
        "minitz-owner-off": "minitz_lifecycle.py off",
        "minitz-owner-on": "minitz_lifecycle.py on",
    }
    for name, command in expected.items():
        text = (LOCAL_AI / name).read_text(encoding="utf-8")
        assert command in text
        assert "biella_customer_handoff.py checkpoint" not in text


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
    assert len(calls) == 3
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


def test_production_writer_has_readiness_gate_and_target_is_canonical():
    unit = (LOCAL_AI / "biella-codex-production.service").read_text(encoding="utf-8")
    target = (LOCAL_AI / "minitz-on.target").read_text(encoding="utf-8")
    assert "ExecStartPre=/usr/local/lib/biella-ai/minitz_lifecycle.py assert-ready" in unit
    assert "Wants=network-online.target docker.service" in target
    assert "biella-codex-production.service" in target
    assert "biella-control-gateway.service" in target
    assert "project-sandbox-broker.service" in target


def test_installer_deploys_lifecycle_controller_entrypoints_and_target():
    installer = (LOCAL_AI / "install-biella-ai.sh").read_text(encoding="utf-8")
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
        "/mnt/biella-extra/minitz-os-sandbox/workspace/repo"
    )
    assert lifecycle.DEFAULT_REPO_ROOT != Path("/root/biella/repos/biella-engine")
