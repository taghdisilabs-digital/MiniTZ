from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]

def module():
    path = ROOT / "ops/workstation/minitz-os-sandbox/attachments.py"
    spec = importlib.util.spec_from_file_location("sandbox_attachments_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_sandbox_control_uses_current_task_not_commit_title():
    api = module()
    source = {"current_execution": {"task_id": "ACTIVE", "task_revision": 2},
              "tasks": [{"task_id": "ACTIVE", "revision": 2, "status": "WORKING", "title": "Current owner task"}]}
    state = api.SandboxControlState(ROOT, {"state": "LOCAL_CAPABILITY_QUALIFIED"},
        program_reader=lambda: source, observer=lambda: {"host_available_bytes": 1234})
    result = state.payload("overview", "Engine")
    assert result["product"] == "MiniTZ OS"
    assert result["task_id"] == "ACTIVE"
    assert result["active_task"] == "Current owner task"
    assert result["progression_mutation"] is False
    assert state.payload("hardware", "Engine")["observation"]["host_available_bytes"] == 1234


def test_coder_handshake_does_not_start_task_or_fetch_quota():
    api = module()
    calls, notices = [], []
    def rpc(method, params):
        calls.append((method, params))
        return {"initialize": {"userAgent": "fixture"}, "config/read": {"config": {}},
                "account/read": {"account": {"type": "chatgpt", "email": "private@example.invalid"}, "requiresOpenaiAuth": True}}[method]
    result = api.qualify_coder_protocol(rpc, lambda method: notices.append(method))
    assert [call[0] for call in calls] == ["initialize", "config/read", "account/read"]
    assert calls[-1][1] == {"refreshToken": False}
    assert notices == ["initialized"]
    assert result["state"] == "PROTOCOL_AUTH_ATTACHED"
    assert result["production_turn_started"] is False
    assert "private@example.invalid" not in json.dumps(result)


def test_coder_missing_auth_is_not_reported_as_ready():
    api = module()
    def rpc(method, params):
        return {"initialize": {}, "config/read": {"config": {}},
                "account/read": {"account": None, "requiresOpenaiAuth": True}}[method]
    assert api.qualify_coder_protocol(rpc, lambda _: None)["state"] == "NEEDS_AUTH"


def test_coder_invalid_protocol_reply_is_not_service_success():
    api = module()
    with pytest.raises(RuntimeError, match="configuration"):
        api.qualify_coder_protocol(lambda *args: {}, lambda _: None)


def test_startup_attachment_module_is_not_shadowed_by_attachment_digest_mapping():
    import ast
    tree = ast.parse((ROOT / "ops/workstation/minitz-os-sandbox/startup.py").read_text())
    imports = {alias.asname or alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            writes = {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
            assert not (imports & writes), "Local variable shadows a startup service module"
