from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / "ops/workstation/minitz-os-sandbox"


def test_minitz_os_sandbox_uses_ubuntu_2604_gpu_and_read_only_host_os():
    dockerfile = (SANDBOX / "Dockerfile").read_text()
    run = (SANDBOX / "run-local.sh").read_text()
    execute = (SANDBOX / "exec-local.sh").read_text()
    assert "FROM ubuntu:26.04" in dockerfile
    for text in (run, execute):
        assert "--gpus all" in text
        assert "--runtime=nvidia" in text
        assert "--network none" not in text
        assert "--security-opt=no-new-privileges:true" not in text
        assert "--cap-drop=ALL" not in text
        assert "/workspace:rw" in text
        assert "/host-vps/usr:ro" in text
        assert "/host-vps/etc/systemd:ro" in text
        assert "TASK_PROGRAM.json:/minitz-live/TASK_PROGRAM.json:ro" in text
        assert "BOOSTER_TASK_LIST.json:/minitz-live/BOOSTER_TASK_LIST.json:ro" in text
        assert "compacted-memory.json:/minitz-live/compacted-memory.json:ro" in text
        assert "current-task.json:/minitz-live/current-task.json:ro" in text
        assert "/root:/host-vps/root" not in text


def test_sandbox_network_is_available_without_owner_authorization_gate():
    local = (SANDBOX / "run-local.sh").read_text()
    networked = (SANDBOX / "run-networked.sh").read_text()
    assert "--network none" not in local
    assert "--network none" not in networked
    assert "EXTERNAL_PROVIDER_USE_REQUIRES_OWNER_AUTHORIZATION" not in networked


def test_execution_policy_requires_sandbox_and_read_only_host_os_reference():
    policy = (ROOT / "ops/workstation/AGENTS.md").read_text()
    for marker in (
        "Ubuntu 26.04 environment",
        "main VPS OS system files",
        "/host-vps",
        "read-only references",
    ):
        assert marker.lower() in policy.lower(), marker


def test_booster_exec_wrapper_mounts_only_selected_booster_worktree():
    text = (SANDBOX / "exec-booster.sh").read_text()
    assert 'BOOSTER="$1"' in text
    assert 'workspace/boosts/$BOOSTER:/workspace/repo:rw' in text
    assert 'workspace:/workspace:rw' not in text
    assert "--network none" not in text
    assert "--security-opt=no-new-privileges:true" not in text
    assert "--cap-drop=ALL" not in text
    assert "BOOSTER_TASK_LIST.json:/minitz-live/BOOSTER_TASK_LIST.json:ro" in text
    assert "context/$BOOSTER.json:/minitz-live/BOOSTER_CONTEXT.json:ro" in text
