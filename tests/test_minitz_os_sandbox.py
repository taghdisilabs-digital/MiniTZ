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



def test_runtime_attaches_github_as_read_only_credential_resource():
    runtime = (SANDBOX / "runtime.sh").read_text()
    assert '/root/.config/gh/hosts.yml:/resources/credentials/github/hosts.yml:ro' in runtime
    assert 'git-credential-github:/usr/local/bin/minitz-git-credential-github:ro' in runtime
    assert 'MINITZ_GITHUB_CREDENTIAL_FILE=/resources/credentials/github/hosts.yml' in runtime
    assert 'GIT_CONFIG_KEY_0=credential.helper' in runtime
    assert 'GIT_CONFIG_VALUE_0=/usr/local/bin/minitz-git-credential-github' in runtime
    assert 'x-access-token@github.com' not in runtime


def test_github_credential_helper_is_host_scoped_and_source_contains_no_secret(tmp_path):
    import os, subprocess
    helper = SANDBOX / "git-credential-github"
    credential = tmp_path / "hosts.yml"
    credential.write_text("github.com:\n    user: ExampleUser\n    oauth_token: fake-test-token\n    git_protocol: https\n")
    env = dict(os.environ, MINITZ_GITHUB_CREDENTIAL_FILE=str(credential))
    good = subprocess.run([str(helper), "get"], input="protocol=https\nhost=github.com\n\n", text=True, capture_output=True, env=env)
    assert good.returncode == 0
    assert "username=x-access-token" in good.stdout
    assert "password=fake-test-token" in good.stdout
    other = subprocess.run([str(helper), "get"], input="protocol=https\nhost=example.com\n\n", text=True, capture_output=True, env=env)
    assert other.returncode == 0 and other.stdout == ""
    assert "fake-test-token" not in helper.read_text()


def test_runtime_wrapper_is_executable():
    import os
    assert os.access(SANDBOX / "runtime.sh", os.X_OK)


def test_runtime_lifecycle_has_no_pause_or_off_gate_files():
    runtime=(SANDBOX/"runtime.sh").read_text()
    startup=(SANDBOX/"startup.py").read_text()
    runner=(ROOT/"ops/local-ai/minitz_production_runner.py").read_text()
    active=runtime+startup+runner
    for forbidden in ("PAUSED_FOR_CUSTOMER", "STOPPED_FOR_MAINTENANCE", "customer-pause-request.json", "minitz-off-request.json", "minitz-off-ack.json"):
        assert forbidden not in active
    assert "send_signal(signal.SIGTERM)" in startup


def test_runtime_auto_mode_matches_resident_local_model_by_digest_not_tag_name():
    runtime=(SANDBOX/"runtime.sh").read_text()
    assert '"http://127.0.0.1:11434/api/tags"' in runtime
    assert 'r.get("digest")==desired' in runtime
    assert 'any(r.get("name")=="qwen3-coder-next:minitz" for r in p.get("models",[]))' not in runtime


def test_runtime_does_not_force_single_qwen_parallel_request():
    runtime=(SANDBOX/"runtime.sh").read_text()
    assert "OLLAMA_NUM_PARALLEL=1" not in runtime
    assert "MINITZ_LOCAL_QWEN_PARALLEL" in runtime


def test_runtime_on_preserves_existing_container_and_reconciles_only_before_new_container():
    runtime = (SANDBOX / "runtime.sh").read_text()
    on_branch = runtime.split("  on)", 1)[1].split("    ;;", 1)[0]
    assert 'exec docker start "$NAME"' in on_branch
    assert "docker rm" not in on_branch
    assert "ensure_installed_source_matches_workspace" in on_branch
    assert "build_release" in on_branch
    assert "install_release" in on_branch
    assert on_branch.index('exec docker start "$NAME"') < on_branch.index("ensure_installed_source_matches_workspace")
    assert on_branch.index("ensure_installed_source_matches_workspace") < on_branch.index("docker run")
