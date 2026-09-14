from __future__ import annotations
import fcntl
import importlib.util
import io
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

def module():
    path=ROOT/"ops/workstation/minitz-os-sandbox/production.py"
    assert path.is_file(), "Sandbox startup has no production handoff implementation"
    spec=importlib.util.spec_from_file_location("minitz_production_handoff_test",path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def fixture(tmp_path):
    repo=tmp_path/"canonical-source"
    (repo/"ops/local-ai").mkdir(parents=True)
    (repo/"ops/local-ai/minitz_production_runner.py").write_text("# existing runner")
    runtime=tmp_path/"existing-runtime";runtime.mkdir()
    (runtime/"accepted.json").write_text('{"status":"accepted"}')
    return repo,runtime


def test_handoff_uses_existing_runner_source_runtime_and_authority(tmp_path):
    api=module();repo,runtime=fixture(tmp_path)
    command,env=api.production_command(repo,runtime,{"MINITZ_TASK_PROGRAM_PATH":"/authority/TASK_PROGRAM.json", "MINITZ_CODEX_EXCLUDE_MODELS":"excluded", "MINITZ_SOURCE_ROOT":"/immutable/release"})
    assert command[-1]=="run"
    assert command[-2]==str(repo/"ops/local-ai/minitz_production_runner.py")
    assert env["MINITZ_RUNTIME_ROOT"]==str(runtime)
    assert env["MINITZ_TASK_PROGRAM_PATH"]=="/authority/TASK_PROGRAM.json"
    assert env["MINITZ_SOURCE_ROOT"]==str(repo)
    assert env["MINITZ_CODEX_EXCLUDE_MODELS"]=="excluded"
    assert "systemctl" not in command


def test_optional_local_failure_does_not_prevent_execution_handoff(tmp_path):
    api=module();repo,runtime=fixture(tmp_path);calls=[]
    class Child: pid=123
    def spawn(command,**kwargs): calls.append((command,kwargs));return Child()
    child,evidence=api.launch_production(repo,runtime,io.StringIO(),env={"LOCAL_QUALITY":"FAIL","GPU_UTILIZATION":"100"},popen=spawn)
    assert child.pid==123 and len(calls)==1
    assert evidence["state"]=="START_REQUESTED"
    assert evidence["functional_acceptance"]=="NOT_YET_OBSERVED"
    assert (runtime/"accepted.json").read_text()=='{"status":"accepted"}'


def test_existing_runner_lock_prevents_duplicate_spawn(tmp_path):
    api=module();repo,runtime=fixture(tmp_path)
    with (runtime/"run.lock").open("a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        child,evidence=api.launch_production(repo,runtime,io.StringIO(),env={},popen=lambda *_a,**_k:pytest.fail("duplicate runner"))
    assert child is None and evidence["state"]=="ALREADY_RUNNING"


def test_production_handoff_has_no_pause_file_authority(tmp_path):
    text=(ROOT/"ops/workstation/minitz-os-sandbox/production.py").read_text()
    assert "customer-pause" not in text
    assert "minitz-off-request" not in text


def test_runtime_mounts_execution_state_writable_without_host_os_admin():
    text=(ROOT/"ops/workstation/minitz-os-sandbox/runtime.sh").read_text()
    assert 'MINITZ_PRODUCTION_AUTORUN=1' in text
    assert '$SANDBOX/workspace:/workspace:rw' in text
    assert '$RUNTIME:$RUNTIME:rw' in text
    assert '/var/run/docker.sock' not in text
    assert '--privileged' not in text
    assert 'MEMORY="${MINITZ_SANDBOX_MEMORY:-28g}"' not in text


def test_executor_bundle_and_local_resource_cli_are_attached():
    text=(ROOT/"ops/workstation/minitz-os-sandbox/runtime.sh").read_text()
    assert '$CODER_DIR:/resources/codex-bin:ro' in text
    assert 'MINITZ_CODEX_BIN=/resources/codex-bin/codex' in text
    assert 'resource-cli.sh:/usr/local/bin/minitz-resource:ro' in text


def test_graceful_signal_handler_never_waits_on_the_child_wait_lock():
    import ast
    tree=ast.parse((ROOT/"ops/workstation/minitz-os-sandbox/startup.py").read_text())
    handler=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=="shutdown")
    assert not any(isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                   and isinstance(node.func.value,ast.Name) and node.func.value.id=="production_child"
                   and node.func.attr in {"wait","kill","terminate"} for node in ast.walk(handler))
