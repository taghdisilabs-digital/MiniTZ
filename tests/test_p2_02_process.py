"""P2-02 bounded managed process execution acceptance tests."""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile

import pytest
import biella
from biella import (
    ArtifactService,
    CallLedgerService,
    CapabilityRef,
    EventLedger,
    FilesystemAdapter,
    FilesystemMode,
    FilesystemObjectStorageBackend,
    FilesystemRoot,
    FilesystemScope,
    GraphRef,
    GraphService,
    ManagedProcessAdapter,
    MemoryObjectStorageBackend,
    NetworkPolicy,
    Node,
    NodeExecutionAttempt,
    NodeExecutionService,
    NodeRef,
    ProcessAuthorityError,
    ProcessContractError,
    ProcessExecutionRequest,
    ProcessFailure,
    ProcessIntegrityError,
    ProcessResourcePolicy,
    ProcessResult,
    ProcessScopeError,
    ProcessStatus,
    ProjectAccess,
    ProjectRef,
    ProjectStore,
    ResourceAllocationRef,
    RunService,
    TaskRevisionService,
    ToolCallRef,
)


ROOT = Path(__file__).resolve().parents[1]


def test_t01_public_managed_process_interfaces_are_active_runtime_exports() -> None:
    expected = {
        "ManagedProcessAdapter",
        "NetworkPolicy",
        "ProcessExecutionRequest",
        "ProcessFailure",
        "ProcessResourcePolicy",
        "ProcessResult",
        "ProcessStatus",
    }
    assert expected.issubset(set(biella.__all__))


@dataclass(frozen=True)
class _Environment:
    database: Path
    access: ProjectAccess
    project_ref: ProjectRef
    objects: FilesystemObjectStorageBackend
    filesystem: FilesystemAdapter
    process: ManagedProcessAdapter
    root: FilesystemRoot
    root_path: Path
    attempt: NodeExecutionAttempt


def _environment(tmp_path: Path, *, namespace: str = "process") -> _Environment:
    database = tmp_path / f"{namespace}.sqlite3"
    registration = ProjectStore(database).create_project(
        namespace=namespace,
        display_name=namespace.title(),
    )
    root_path = tmp_path / f"{namespace}-root"
    root_path.mkdir()
    objects = FilesystemObjectStorageBackend(tmp_path / f"{namespace}-objects")
    filesystem = FilesystemAdapter(database, objects)
    filesystem_capabilities = filesystem.register_capabilities(registration.access)
    process = ManagedProcessAdapter(
        database,
        objects,
        inherited_environment={"LANG": "C.UTF-8", "SAFE_INHERITED": "visible"},
    )
    process_capabilities = process.register_capabilities(registration.access)
    capabilities = tuple(sorted((*filesystem_capabilities, *process_capabilities)))
    task = TaskRevisionService(database).create_task(
        registration.access,
        project_ref=registration.project.project_ref,
        idempotency_key="managed-process-task",
        task_type="process.execute",
        objective="Execute bounded managed process tests",
        required_capabilities=capabilities,
        input_refs=(),
        output_contract={"result": "schema://biella/process-result/1"},
        constraints={},
        side_effect_authority="PROJECT_WRITE",
        data_policy_ref=None,
        egress_policy_ref=None,
        evidence_requirements=("tool-call", "artifact", "content-ref"),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(registration.access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        registration.access,
        run.run_ref,
        owner_ref="controller://managed-process-tests",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(registration.project.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "TOOL",
        capabilities,
        (),
        (),
        {"result": "schema://biella/process-result/1"},
        None,
        "PROJECT_WRITE",
        {},
        ("tool-call", "artifact", "content-ref"),
    )
    GraphService(database).create_graph(
        registration.access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(node,),
        compiler_identity=None,
        compiler_version=None,
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    executions.prepare_run(registration.access, run.run_ref)
    attempt = executions.lease_node(
        registration.access,
        node.node_ref,
        authority_attempt=run_attempt,
        owner_ref="executor://managed-process-tests",
        lease_seconds=1800,
        idempotency_key="managed-process-node-lease",
    )
    executions.start_node(
        registration.access,
        attempt,
        idempotency_key="managed-process-node-start",
    )
    root = filesystem.register_root(
        registration.access,
        path=root_path,
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_WRITE,
        allow_remove=True,
        idempotency_key="managed-process-root",
    )
    return _Environment(
        database,
        registration.access,
        registration.project.project_ref,
        objects,
        filesystem,
        process,
        root,
        root_path,
        attempt,
    )


def _request(
    env: _Environment,
    *,
    executable: str = sys.executable,
    argv: tuple[str, ...] = ("-c", "print('ok')"),
    **changes: object,
) -> ProcessExecutionRequest:
    values: dict[str, object] = {
        "project_ref": env.project_ref,
        "working_root_ref": env.root.root_ref,
        "working_directory": ".",
        "executable": executable,
        "argv": argv,
        "inherited_environment": ("LANG",),
        "environment_overrides": {},
        "secret_environment_refs": {},
        "timeout_seconds": 10.0,
        "termination_grace_seconds": 0.2,
        "stdout_limit_bytes": 1024 * 1024,
        "stderr_limit_bytes": 1024 * 1024,
        "network_policy": NetworkPolicy.INHERIT,
        "resource_policy": ProcessResourcePolicy(),
        "shell": False,
    }
    values.update(changes)
    return ProcessExecutionRequest(**values)  # type: ignore[arg-type]


class _InjectedManagedLaunchCrash(BaseException):
    """Test-only abrupt caller loss that bypasses ordinary Exception cleanup."""


_MANAGED_PROCESS_TABLES = (
    "managed_process_claims",
    "managed_process_launches",
    "managed_process_prepared_executions",
    "managed_process_executions",
    "managed_process_results",
    "managed_process_recovery_heads",
    "managed_process_recovery_events",
    "managed_process_recovery_releases",
)


def _managed_process_counts(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(database)
    try:
        counts: dict[str, int] = {}
        for table in _MANAGED_PROCESS_TABLES:
            row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            assert row is not None
            counts[table] = int(row[0])
        return counts
    finally:
        connection.close()


def _only_managed_call_ref(env: _Environment) -> ToolCallRef:
    connection = sqlite3.connect(env.database)
    try:
        rows = connection.execute(
            "SELECT call_id FROM managed_process_claims"
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == 1
    return ToolCallRef(env.project_ref, str(rows[0][0]))


def _wait_for_file_bytes(path: Path, expected: bytes) -> None:
    deadline = time.monotonic() + 3.0
    observed: bytes | None = None
    while time.monotonic() < deadline:
        try:
            observed = path.read_bytes()
        except FileNotFoundError:
            observed = None
        if observed == expected:
            return
        time.sleep(0.01)
    assert observed == expected


def _assert_identity_stopped(
    process: ManagedProcessAdapter,
    identity: biella.ManagedProcessIdentity,
) -> None:
    deadline = time.monotonic() + 3.0
    while (
        process._owned_group_has_live_members(identity)
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)
    assert not process._owned_group_has_live_members(identity)
    assert _process_state(identity.pid) in {None, "Z"}


def test_t02_registers_direct_and_explicit_shell_capabilities(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    implementations = env.process.register_capabilities(env.access)
    assert set(implementations) == {
        CapabilityRef("process.execute", "1.0.0"),
        CapabilityRef("process.shell", "1.0.0"),
    }
    assert implementations[CapabilityRef("process.execute", "1.0.0")].tool_ref == "tool://biella/process/execute"
    assert implementations[CapabilityRef("process.shell", "1.0.0")].tool_ref == "tool://biella/process/shell"


def test_t03_success_nonzero_and_missing_executable_have_exact_taxonomy(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    success = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=("-c", "import sys; print('stdout-value'); print('stderr-value', file=sys.stderr)"),
        ),
        idempotency_key="process-success",
    )
    assert success.status is ProcessStatus.SUCCEEDED
    assert success.failure is None
    assert success.exit_code == 0
    assert env.objects.read(success.stdout_ref) == b"stdout-value\n"
    assert env.objects.read(success.stderr_ref) == b"stderr-value\n"
    assert success.process_identity is not None
    assert success.process_identity.pid == success.process_identity.process_group_id
    call = CallLedgerService(env.database).get_tool_call(env.access, success.tool_call_ref)
    artifact = ArtifactService(env.database).get_artifact(env.access, success.artifact_ref)
    assert call.status == "SUCCEEDED"
    assert call.node_attempt_id == env.attempt.attempt_id
    assert artifact.content_ref == success.result_ref
    assert success.request_ref in artifact.source_content_refs
    assert success.stdout_ref in artifact.source_content_refs
    start_event = EventLedger(env.database).get_event(env.access, call.event_ref)
    terminal_event = EventLedger(env.database).get_event(env.access, call.state.status_event_ref)
    assert start_event.event_type == "TOOL_CALL"
    assert terminal_event.event_type == "TOOL_CALL_TERMINAL"
    assert start_event.node_ref == terminal_event.node_ref == env.attempt.node_ref
    nonzero = env.process.execute(
        env.access,
        env.attempt,
        _request(env, argv=("-c", "raise SystemExit(7)")),
        idempotency_key="process-nonzero",
    )
    assert nonzero.status is ProcessStatus.FAILED
    assert nonzero.failure is ProcessFailure.EXIT_NONZERO
    assert nonzero.exit_code == 7
    assert CallLedgerService(env.database).get_tool_call(env.access, nonzero.tool_call_ref).status == "FAILED"
    missing = env.process.execute(
        env.access,
        env.attempt,
        _request(env, executable="/definitely/missing/biella-tool", argv=()),
        idempotency_key="process-missing",
    )
    assert missing.failure is ProcessFailure.EXECUTABLE_NOT_FOUND
    assert missing.process_identity is None
    assert missing.termination_method == "NOT_STARTED"


def test_t04_argv_is_not_shell_interpreted_and_shell_is_explicit_capability(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    escaped = tmp_path / "must-not-exist"
    literal = f"$(touch {escaped}); value with spaces && metacharacters"
    direct = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=("-c", "import sys; print(sys.argv[1])", literal),
        ),
        idempotency_key="argv-not-shell",
    )
    assert env.objects.read(direct.stdout_ref) == (literal + "\n").encode()
    assert not escaped.exists()
    with pytest.raises(ProcessAuthorityError):
        env.process.execute(
            env.access,
            env.attempt,
            _request(env, executable="/bin/sh", argv=("-c", "printf denied")),
            idempotency_key="implicit-shell-denied",
        )
    explicit = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            executable="/bin/sh",
            argv=("-c", "printf shell-ok"),
            shell=True,
        ),
        idempotency_key="explicit-shell",
    )
    assert explicit.status is ProcessStatus.SUCCEEDED
    assert env.objects.read(explicit.stdout_ref) == b"shell-ok"
    call = CallLedgerService(env.database).get_tool_call(env.access, explicit.tool_call_ref)
    assert call.capability_ref == CapabilityRef("process.shell", "1.0.0")


def test_t05_output_limits_are_explicit_and_large_output_is_streamed(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    limited = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=("-c", "import os,time; os.write(1, b'x' * 200000); time.sleep(2)"),
            stdout_limit_bytes=1024,
        ),
        idempotency_key="output-limit",
    )
    assert limited.status is ProcessStatus.FAILED
    assert limited.failure is ProcessFailure.OUTPUT_LIMIT
    assert limited.stdout_truncated
    assert limited.stdout_ref.size_bytes == 1024
    assert limited.termination_method in {
        "SIGTERM_PROCESS_GROUP",
        "SIGTERM_THEN_SIGKILL_PROCESS_GROUP",
        "ALREADY_EXITED",
    }
    quick_overflow = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=("-c", "import os; os.write(1, b'q' * 200000)"),
            stdout_limit_bytes=1024,
        ),
        idempotency_key="quick-output-limit",
    )
    assert quick_overflow.status is ProcessStatus.FAILED
    assert quick_overflow.failure is ProcessFailure.OUTPUT_LIMIT
    assert quick_overflow.stdout_truncated
    large_size = 8 * 1024 * 1024 + 123
    large = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=("-c", f"import os; os.write(1, b'z' * {large_size})"),
            stdout_limit_bytes=large_size,
        ),
        idempotency_key="large-streaming-output",
    )
    assert large.status is ProcessStatus.SUCCEEDED
    assert not large.stdout_truncated
    assert large.stdout_ref.size_bytes == large_size
    assert large.stdout_preview.startswith("z" * 100)
    assert "[bounded tail]" in large.stdout_preview
    with env.objects.open(large.stdout_ref) as reader:
        observed = 0
        while chunk := reader.read(64 * 1024):
            observed += len(chunk)
    assert observed == large_size


def _process_state(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except FileNotFoundError:
        return None
    return raw.rsplit(")", 1)[1].strip().split()[0]


def test_t06_timeout_terminates_owned_child_tree_with_forced_escalation(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    code = (
        "import signal,subprocess,sys,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "child=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)']); "
        "print(child.pid, flush=True); time.sleep(30)"
    )
    result = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=("-c", code),
            timeout_seconds=0.3,
            termination_grace_seconds=0.1,
        ),
        idempotency_key="timeout-process-tree",
    )
    assert result.status is ProcessStatus.TIMED_OUT
    assert result.failure is ProcessFailure.TIMEOUT
    assert result.termination_method == "SIGTERM_THEN_SIGKILL_PROCESS_GROUP"
    assert result.process_tree_state == "OWNED_PROCESS_GROUP_TERMINATED_NO_LIVE_MEMBERS"
    child_pid = int(env.objects.read(result.stdout_ref).strip())
    deadline = time.monotonic() + 2
    while _process_state(child_pid) not in {None, "Z"} and time.monotonic() < deadline:
        time.sleep(0.02)
    assert _process_state(child_pid) in {None, "Z"}
    assert CallLedgerService(env.database).get_tool_call(env.access, result.tool_call_ref).status == "TIMED_OUT"
    parent_exits_first = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=(
                "-c",
                "import signal,subprocess,sys; child=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)']); print(child.pid, flush=True)",
            ),
            timeout_seconds=0.3,
            termination_grace_seconds=0.1,
        ),
        idempotency_key="parent-exits-before-child",
    )
    assert parent_exits_first.status is ProcessStatus.TIMED_OUT
    assert parent_exits_first.failure is ProcessFailure.TIMEOUT
    assert parent_exits_first.termination_method == "SIGTERM_THEN_SIGKILL_PROCESS_GROUP"
    orphan_pid = int(env.objects.read(parent_exits_first.stdout_ref).strip())
    assert _process_state(orphan_pid) in {None, "Z"}


def test_t07_cancellation_is_truthful_and_stale_identity_never_kills_unrelated_process(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    start = time.monotonic()
    cancelled = env.process.execute(
        env.access,
        env.attempt,
        _request(env, argv=("-c", "import time; time.sleep(30)")),
        idempotency_key="cancel-managed-process",
        cancelled=lambda: time.monotonic() - start > 0.15,
    )
    assert cancelled.status is ProcessStatus.CANCELLED
    assert cancelled.failure is ProcessFailure.CANCELLED
    assert cancelled.termination_method == "SIGTERM_PROCESS_GROUP"
    assert cancelled.process_tree_state == "OWNED_PROCESS_GROUP_TERMINATED_NO_LIVE_MEMBERS"
    assert CallLedgerService(env.database).get_tool_call(env.access, cancelled.tool_call_ref).status == "CANCELLED"
    assert cancelled.process_identity is not None
    unrelated = subprocess.Popen(("/bin/sleep", "30"), start_new_session=True)
    try:
        stale = biella.ManagedProcessIdentity(
            "pexec_" + "0" * 32,
            env.project_ref,
            cancelled.tool_call_ref,
            unrelated.pid,
            unrelated.pid,
            env.process._boot_id(),
            env.process._start_ticks(unrelated.pid) + 1,
            "0" * 64,
            0,
            0,
            cancelled.started_at,
        )
        with pytest.raises(ProcessAuthorityError):
            env.process._terminate_owned(unrelated, stale, 0.01)
        assert unrelated.poll() is None
    finally:
        os.killpg(unrelated.pid, 9)
        unrelated.wait(timeout=5)


def test_t08_environment_allowlist_and_secret_values_never_persist(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    secret = "super-secret-value-12345"
    request = _request(
        env,
        argv=(
            "-c",
            "import os; print(os.environ['SAFE']); print(os.environ['SAFE_INHERITED']); print(os.environ['API_TOKEN'])",
        ),
        inherited_environment=("SAFE_INHERITED",),
        environment_overrides={"SAFE": "configured"},
        secret_environment_refs={"API_TOKEN": "secret://test/api-token"},
    )
    result = env.process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="secret-environment",
        secret_values={"API_TOKEN": secret},
    )
    output = env.objects.read(result.stdout_ref)
    assert b"configured\nvisible\n[REDACTED]\n" == output
    assert secret.encode() not in env.database.read_bytes()
    for path in (tmp_path / "process-objects").rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes()
    request_payload = json.loads(env.objects.read(result.request_ref))
    assert request_payload["secret_environment_refs"] == {"API_TOKEN": "secret://test/api-token"}
    assert secret not in json.dumps(request_payload)
    with pytest.raises(ProcessContractError):
        _request(env, environment_overrides={"API_TOKEN": "not-allowed-here"})
    with pytest.raises(ProcessContractError):
        _request(env, inherited_environment=("ACCESS_TOKEN",))


def test_t09_working_directory_and_project_scope_are_exact(tmp_path: Path) -> None:
    env = _environment(tmp_path / "alpha", namespace="process-alpha")
    beta = _environment(tmp_path / "beta", namespace="process-beta")
    work = env.root_path / "work"
    work.mkdir()
    result = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=("-c", "from pathlib import Path; Path('generated.txt').write_text('generated')"),
            working_directory="work",
        ),
        idempotency_key="bounded-working-directory",
    )
    assert result.status is ProcessStatus.SUCCEEDED
    assert (work / "generated.txt").read_text() == "generated"
    with pytest.raises(ProcessContractError):
        _request(env, working_directory="../escape")
    with pytest.raises(ProcessScopeError):
        _request(env, working_root_ref=beta.root.root_ref)
    with pytest.raises(ProcessScopeError):
        _request(
            env,
            resource_allocation_ref=ResourceAllocationRef(beta.project_ref, "ral_" + "0" * 32),
        )
    read_only_path = tmp_path / "read-only-process-root"
    read_only_path.mkdir()
    read_only = env.filesystem.register_root(
        env.access,
        path=read_only_path,
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_ONLY,
        allow_remove=False,
        idempotency_key="read-only-process-root",
    )
    with pytest.raises(ProcessAuthorityError):
        env.process.execute(
            env.access,
            env.attempt,
            _request(env, working_root_ref=read_only.root_ref),
            idempotency_key="read-only-process-denied",
        )


def test_t10_network_and_resource_enforcement_are_truthful(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    denied = env.process.execute(
        env.access,
        env.attempt,
        _request(env, network_policy=NetworkPolicy.NONE),
        idempotency_key="network-none-unsupported",
    )
    assert denied.failure is ProcessFailure.POLICY_DENIED
    assert denied.process_identity is None
    assert denied.network_enforcement == "UNSUPPORTED_NONE_POLICY_DENIED"
    restricted = env.process.execute(
        env.access,
        env.attempt,
        _request(env, network_policy=NetworkPolicy.RESTRICTED),
        idempotency_key="network-restricted-unsupported",
    )
    assert restricted.failure is ProcessFailure.POLICY_DENIED
    assert restricted.network_enforcement == "UNSUPPORTED_RESTRICTED_POLICY_DENIED"
    with pytest.raises(ProcessAuthorityError, match="ResourceAllocation"):
        env.process.execute(
            env.access,
            env.attempt,
            _request(
                env,
                resource_allocation_ref=ResourceAllocationRef(env.project_ref, "ral_" + "0" * 32),
            ),
            idempotency_key="missing-resource-allocation",
        )
    limited = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            resource_policy=ProcessResourcePolicy(
                cpu_seconds=2,
                memory_bytes=256 * 1024 * 1024,
                file_size_bytes=1024 * 1024,
                process_count=32,
            ),
        ),
        idempotency_key="configured-resource-limits",
    )
    assert limited.status is ProcessStatus.SUCCEEDED
    assert limited.resource_enforcement["cpu_seconds"] == "ENFORCED_RLIMIT_CPU"
    assert limited.resource_enforcement["memory_bytes"] == "ENFORCED_RLIMIT_AS"
    assert limited.resource_enforcement["file_size_bytes"] == "ENFORCED_RLIMIT_FSIZE"
    assert limited.resource_enforcement["process_count"] == "CONFIGURED_RLIMIT_ROOT_EFFECT_NOT_GUARANTEED"


def test_t11_concurrent_processes_and_generated_file_artifact_capture(tmp_path: Path) -> None:
    env = _environment(tmp_path)

    def invoke(index: int) -> ProcessResult:
        return env.process.execute(
            env.access,
            env.attempt,
            _request(env, argv=("-c", f"import time; time.sleep(0.2); print({index})")),
            idempotency_key=f"concurrent-process-{index}",
        )

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(invoke, (1, 2)))
    elapsed = time.monotonic() - started
    assert elapsed < 0.75
    assert {env.objects.read(item.stdout_ref) for item in results} == {b"1\n", b"2\n"}
    generated_process = env.process.execute(
        env.access,
        env.attempt,
        _request(env, argv=("-c", "from pathlib import Path; Path('captured.txt').write_bytes(b'exact-generated')")),
        idempotency_key="generated-process-file",
    )
    assert generated_process.status is ProcessStatus.SUCCEEDED
    captured = env.filesystem.read(
        env.access,
        env.attempt,
        root_ref=env.root.root_ref,
        path="captured.txt",
        media_type="application/octet-stream",
        idempotency_key="capture-generated-file",
    )
    assert env.objects.read(captured.output_ref) == b"exact-generated"
    assert ArtifactService(env.database).get_artifact(env.access, captured.artifact_ref).content_ref == captured.output_ref


def test_t12_restart_idempotency_and_process_identity_never_becomes_run_authority(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    request = _request(env, argv=("-c", "print('restart')"))
    original = env.process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="restart-process",
    )
    restarted = ManagedProcessAdapter(
        env.database,
        FilesystemObjectStorageBackend(tmp_path / "process-objects"),
        inherited_environment={"LANG": "C.UTF-8", "SAFE_INHERITED": "visible"},
    )
    recovered = restarted.get_result(env.access, original.tool_call_ref)
    replay = restarted.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="restart-process",
    )
    assert recovered == original
    assert replay == original
    assert recovered.process_identity is not None
    assert not restarted._identity_is_current(recovered.process_identity)
    with pytest.raises(biella.ProcessConflictError):
        restarted.execute(
            env.access,
            env.attempt,
            _request(env, argv=("-c", "print('changed')")),
            idempotency_key="restart-process",
        )
    connection = sqlite3.connect(env.database)
    connection.execute("DROP TRIGGER managed_process_results_no_update")
    connection.execute(
        "UPDATE managed_process_results SET record_sha256=? WHERE call_id=?",
        ("0" * 64, original.tool_call_ref.call_id),
    )
    connection.commit()
    connection.close()
    with pytest.raises(ProcessIntegrityError):
        restarted.get_result(env.access, original.tool_call_ref)


def test_t13_stdin_split_secret_redaction_and_observed_resource_limit(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    binary = env.process.execute(
        env.access,
        env.attempt,
        _request(env, argv=("-c", "import os; os.write(1, b'a\\x00b\\x01c')")),
        idempotency_key="binary-output-text-preview",
    )
    assert env.objects.read(binary.stdout_ref) == b"a\x00b\x01c"
    assert binary.stdout_preview == "a.b.c"
    stdin_ref = env.objects.put(b"bounded stdin bytes", media_type="application/octet-stream")
    stdin_result = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=("-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read().upper())"),
            stdin_ref=stdin_ref,
        ),
        idempotency_key="content-ref-stdin",
    )
    assert env.objects.read(stdin_result.stdout_ref) == b"BOUNDED STDIN BYTES"
    call = CallLedgerService(env.database).get_tool_call(env.access, stdin_result.tool_call_ref)
    artifact = ArtifactService(env.database).get_artifact(env.access, stdin_result.artifact_ref)
    assert stdin_ref in call.input_refs
    assert stdin_ref in artifact.source_content_refs

    secret = "split-secret-value-across-selector-reads"
    split_result = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=(
                "-c",
                "import os,time; value=os.environ['RUNTIME_SECRET'].encode(); os.write(1,b'before:'+value[:12]); time.sleep(.1); os.write(1,value[12:]+b':after')",
            ),
            secret_environment_refs={"RUNTIME_SECRET": "secret://test/split-secret"},
        ),
        idempotency_key="split-secret-redaction",
        secret_values={"RUNTIME_SECRET": secret},
    )
    assert env.objects.read(split_result.stdout_ref) == b"before:[REDACTED]:after"
    assert secret.encode() not in env.database.read_bytes()

    limited = env.process.execute(
        env.access,
        env.attempt,
        _request(
            env,
            argv=("-c", "while True: pass"),
            timeout_seconds=5,
            resource_policy=ProcessResourcePolicy(cpu_seconds=1),
        ),
        idempotency_key="observed-cpu-limit",
    )
    assert limited.status is ProcessStatus.FAILED
    assert limited.failure is ProcessFailure.RESOURCE_LIMIT
    assert limited.signal_number == signal.SIGXCPU


def test_t14_manifest_tamper_and_durable_history_erasure_fail_closed(tmp_path: Path) -> None:
    tampered = _environment(tmp_path / "tampered", namespace="process-tampered")
    result = tampered.process.execute(
        tampered.access,
        tampered.attempt,
        _request(tampered, argv=("-c", "print('tamper-resistant')")),
        idempotency_key="tamper-resistant-result",
    )
    connection = sqlite3.connect(tampered.database)
    row = connection.execute(
        "SELECT result_json FROM managed_process_results WHERE call_id=?",
        (result.tool_call_ref.call_id,),
    ).fetchone()
    assert row is not None
    payload = json.loads(row[0])
    payload["termination_method"] = "FORGED_TERMINATION"
    forged_json = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    forged_sha = hashlib.sha256(forged_json.encode()).hexdigest()
    connection.execute("DROP TRIGGER managed_process_results_no_update")
    connection.execute(
        "UPDATE managed_process_results SET result_json=?,record_sha256=? WHERE call_id=?",
        (forged_json, forged_sha, result.tool_call_ref.call_id),
    )
    connection.commit()
    connection.close()
    with pytest.raises(ProcessIntegrityError, match="manifest differ"):
        tampered.process.get_result(tampered.access, result.tool_call_ref)

    erased = _environment(tmp_path / "erased", namespace="process-erased")
    erased_result = erased.process.execute(
        erased.access,
        erased.attempt,
        _request(erased, argv=("-c", "print('durable-history')")),
        idempotency_key="durable-history",
    )
    connection = sqlite3.connect(erased.database)
    connection.execute("DROP TRIGGER managed_process_claims_no_delete")
    connection.execute(
        "DELETE FROM managed_process_claims WHERE call_id=?",
        (erased_result.tool_call_ref.call_id,),
    )
    connection.commit()
    connection.close()
    with pytest.raises(ProcessIntegrityError, match="history is missing"):
        erased.process.get_result(erased.access, erased_result.tool_call_ref)


def test_t15_type_build_exact_wheel_and_separate_installed_restart() -> None:
    source_paths = (
        ROOT / "src/biella/process.py",
        ROOT / "tests/test_p2_02_process.py",
        ROOT / "tests/fixtures/p2_02_installed_writer.py",
        ROOT / "tests/fixtures/p2_02_installed_reader.py",
    )
    prohibited = (
        "TO" "DO",
        "FIX" "ME",
        "place" "holder",
        "pytest.mark." "skip",
        "@unittest." "skip",
        "Not" "Implemented",
    )
    for path in source_paths:
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        assert all(marker not in source for marker in prohibited)
    active_runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src/biella").glob("*.py"))
        if path.name != "migration.py"
    )
    assert "QuarantineRef" not in active_runtime
    typecheck = subprocess.run(
        (sys.executable, "-m", "mypy", "--strict", "src"),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert typecheck.returncode == 0, f"{typecheck.stdout}\n{typecheck.stderr}"
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary = Path(temporary_directory)
        wheel_root = temporary / "wheel"
        wheel_root.mkdir()
        build = subprocess.run(
            (
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(wheel_root),
            ),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert build.returncode == 0, f"{build.stdout}\n{build.stderr}"
        wheels = tuple(wheel_root.glob("biella_engine-*.whl"))
        assert len(wheels) == 1
        wheel = wheels[0]
        package_paths = tuple(sorted((ROOT / "src/biella").glob("*.py")))
        with zipfile.ZipFile(wheel) as archive:
            wheel_names = {
                name
                for name in archive.namelist()
                if name.startswith("biella/") and name.endswith(".py")
            }
            assert wheel_names == {f"biella/{path.name}" for path in package_paths}
            for path in package_paths:
                wheel_sha = hashlib.sha256(archive.read(f"biella/{path.name}")).hexdigest()
                assert wheel_sha == hashlib.sha256(path.read_bytes()).hexdigest()
        installed = temporary / "installed"
        install = subprocess.run(
            (
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(installed),
                str(wheel),
            ),
            cwd=temporary,
            check=False,
            capture_output=True,
            text=True,
        )
        assert install.returncode == 0, f"{install.stdout}\n{install.stderr}"
        process_root = temporary / "process-root"
        process_root.mkdir()
        environment = os.environ.copy()
        environment.update(
            {
                "BIELLA_DATABASE": str(temporary / "restart.sqlite3"),
                "BIELLA_PROCESS_ROOT": str(process_root),
                "BIELLA_OBJECT_ROOT": str(temporary / "objects"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(installed),
            }
        )
        writer = subprocess.run(
            (sys.executable, str(ROOT / "tests/fixtures/p2_02_installed_writer.py")),
            cwd=temporary,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert writer.returncode == 0, f"{writer.stdout}\n{writer.stderr}"
        identity = json.loads(writer.stdout)
        assert (process_root / "generated.txt").read_bytes() == b"installed process stdin"
        environment["BIELLA_EXPECTED"] = json.dumps(identity, sort_keys=True)
        reader = subprocess.run(
            (sys.executable, str(ROOT / "tests/fixtures/p2_02_installed_reader.py")),
            cwd=temporary,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert reader.returncode == 0, f"{reader.stdout}\n{reader.stderr}"
        observed = json.loads(reader.stdout)
        assert observed["artifact_ref"] == identity["artifact_ref"]
        assert observed["process_record_sha256"] == identity["process_record_sha256"]
        assert observed["record_sha256"] == identity["record_sha256"]


def test_t16_expected_executable_digest_mismatch_never_reaches_target(
    tmp_path: Path,
) -> None:
    env = _environment(tmp_path)
    marker = env.root_path / "digest-mismatch-target-ran"
    request = _request(
        env,
        argv=(
            "-c",
            "from pathlib import Path; Path('digest-mismatch-target-ran').write_text('ran')",
        ),
        expected_executable_sha256="0" * 64,
    )

    with pytest.raises(
        ProcessAuthorityError,
        match="differs from its expected digest",
    ):
        env.process.execute(
            env.access,
            env.attempt,
            request,
            idempotency_key="expected-executable-digest-mismatch",
        )

    call_ref = _only_managed_call_ref(env)
    recovered = env.process.get_result(env.access, call_ref)
    replay = env.process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="expected-executable-digest-mismatch",
    )
    assert not marker.exists()
    assert recovered == replay
    assert recovered.status is ProcessStatus.FAILED
    assert recovered.failure is ProcessFailure.RECOVERY_UNCERTAIN
    assert recovered.process_identity is None
    assert recovered.termination_method == "RECOVERY_DUPLICATE_LAUNCH_SUPPRESSED"
    assert recovered.process_tree_state == "RECOVERY_GATE_CLOSED_BEFORE_PREPARATION_NOT_RETRIED"
    assert _managed_process_counts(env.database) == {
        "managed_process_claims": 1,
        "managed_process_launches": 1,
        "managed_process_prepared_executions": 0,
        "managed_process_executions": 0,
        "managed_process_results": 1,
        "managed_process_recovery_heads": 1,
        "managed_process_recovery_events": 1,
        "managed_process_recovery_releases": 0,
    }


def test_t17_actual_execve_failure_is_prepared_only_spawn_failure(
    tmp_path: Path,
) -> None:
    env = _environment(tmp_path)
    invalid_executable = tmp_path / "invalid-executable"
    invalid_executable.write_bytes(b"\x7fELFnot-an-executable-image\n")
    invalid_executable.chmod(0o700)
    marker = env.root_path / "invalid-executable-target-ran"
    request = _request(
        env,
        executable=str(invalid_executable),
        argv=(str(marker),),
    )

    result = env.process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="actual-execve-failure",
    )
    replay = env.process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="actual-execve-failure",
    )
    prepared = env.process._prepared_identity_for_call(result.tool_call_ref)

    assert not marker.exists()
    assert replay == result
    assert result.status is ProcessStatus.FAILED
    assert result.failure is ProcessFailure.SPAWN_FAILED
    assert result.process_identity is None
    assert prepared is not None
    _assert_identity_stopped(env.process, prepared)
    assert _managed_process_counts(env.database) == {
        "managed_process_claims": 1,
        "managed_process_launches": 1,
        "managed_process_prepared_executions": 1,
        "managed_process_executions": 0,
        "managed_process_results": 1,
        "managed_process_recovery_heads": 0,
        "managed_process_recovery_events": 0,
        "managed_process_recovery_releases": 0,
    }


def test_t18_crash_after_prepared_identity_keeps_gate_closed_and_replays_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _environment(tmp_path)
    marker = env.root_path / "prepared-gate-target-ran"
    request = _request(
        env,
        argv=(
            "-c",
            "from pathlib import Path; Path('prepared-gate-target-ran').write_text('ran')",
        ),
    )
    original_prepare = env.process._prepare_identity
    prepared_identities: list[biella.ManagedProcessIdentity] = []

    def crash_after_prepare(
        access: ProjectAccess,
        call_ref: ToolCallRef,
        process: subprocess.Popen[bytes],
        executable_sha256: str,
        executable_state: os.stat_result,
        started_at: str,
    ) -> biella.ManagedProcessIdentity:
        identity = original_prepare(
            access,
            call_ref,
            process,
            executable_sha256,
            executable_state,
            started_at,
        )
        prepared_identities.append(identity)
        raise _InjectedManagedLaunchCrash(
            "crash after prepared identity before gate release"
        )

    monkeypatch.setattr(env.process, "_prepare_identity", crash_after_prepare)
    with pytest.raises(
        _InjectedManagedLaunchCrash,
        match="before gate release",
    ):
        env.process.execute(
            env.access,
            env.attempt,
            request,
            idempotency_key="crash-after-prepared-identity",
        )

    call_ref = _only_managed_call_ref(env)
    recovered = env.process.get_result(env.access, call_ref)
    replay = env.process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="crash-after-prepared-identity",
    )
    assert len(prepared_identities) == 1
    assert env.process._prepared_identity_for_call(call_ref) == prepared_identities[0]
    assert env.process._execution_identity_for_call(call_ref) is None
    assert not marker.exists()
    assert replay == recovered
    assert recovered.status is ProcessStatus.FAILED
    assert recovered.failure is ProcessFailure.RECOVERY_UNCERTAIN
    assert recovered.process_identity is None
    assert recovered.termination_method.startswith("RECOVERY_")
    _assert_identity_stopped(env.process, prepared_identities[0])
    assert _managed_process_counts(env.database) == {
        "managed_process_claims": 1,
        "managed_process_launches": 1,
        "managed_process_prepared_executions": 1,
        "managed_process_executions": 0,
        "managed_process_results": 1,
        "managed_process_recovery_heads": 1,
        "managed_process_recovery_events": 1,
        "managed_process_recovery_releases": 0,
    }


def test_t19_crash_after_exec_ack_is_fenced_without_duplicate_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _environment(tmp_path)
    marker = env.root_path / "exec-ack-target-count"
    request = _request(
        env,
        argv=(
            "-c",
            "from pathlib import Path; import time; p=Path('exec-ack-target-count'); f=p.open('a'); f.write('target\\n'); f.flush(); f.close(); time.sleep(30)",
        ),
        timeout_seconds=5.0,
    )
    acknowledged_identities: list[biella.ManagedProcessIdentity] = []

    def crash_before_confirmation(
        identity: biella.ManagedProcessIdentity,
    ) -> biella.ManagedProcessIdentity:
        acknowledged_identities.append(identity)
        _wait_for_file_bytes(marker, b"target\n")
        raise _InjectedManagedLaunchCrash(
            "crash after exec acknowledgement before confirmation"
        )

    monkeypatch.setattr(
        env.process,
        "_persist_execution_identity",
        crash_before_confirmation,
    )
    with pytest.raises(
        _InjectedManagedLaunchCrash,
        match="before confirmation",
    ):
        env.process.execute(
            env.access,
            env.attempt,
            request,
            idempotency_key="crash-after-exec-ack",
        )

    call_ref = _only_managed_call_ref(env)
    recovered = env.process.get_result(env.access, call_ref)
    replay = env.process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="crash-after-exec-ack",
    )
    assert len(acknowledged_identities) == 1
    assert env.process._prepared_identity_for_call(call_ref) == acknowledged_identities[0]
    assert env.process._execution_identity_for_call(call_ref) is None
    assert marker.read_bytes() == b"target\n"
    assert replay == recovered
    assert recovered.status is ProcessStatus.FAILED
    assert recovered.failure is ProcessFailure.RECOVERY_UNCERTAIN
    assert recovered.process_identity is None
    assert recovered.termination_method.startswith("RECOVERY_SIGTERM")
    _assert_identity_stopped(env.process, acknowledged_identities[0])
    assert _managed_process_counts(env.database) == {
        "managed_process_claims": 1,
        "managed_process_launches": 1,
        "managed_process_prepared_executions": 1,
        "managed_process_executions": 0,
        "managed_process_results": 1,
        "managed_process_recovery_heads": 1,
        "managed_process_recovery_events": 1,
        "managed_process_recovery_releases": 0,
    }


def test_t20_crash_after_confirmed_execution_recovers_exact_identity_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _environment(tmp_path)
    marker = env.root_path / "confirmed-target-count"
    request = _request(
        env,
        argv=(
            "-c",
            "from pathlib import Path; import time; p=Path('confirmed-target-count'); f=p.open('a'); f.write('target\\n'); f.flush(); f.close(); time.sleep(30)",
        ),
        timeout_seconds=5.0,
    )
    original_persist = env.process._persist_execution_identity
    confirmed_identities: list[biella.ManagedProcessIdentity] = []

    def crash_after_confirmation(
        identity: biella.ManagedProcessIdentity,
    ) -> biella.ManagedProcessIdentity:
        confirmed = original_persist(identity)
        confirmed_identities.append(confirmed)
        _wait_for_file_bytes(marker, b"target\n")
        raise _InjectedManagedLaunchCrash(
            "crash after confirmed execution before result"
        )

    monkeypatch.setattr(
        env.process,
        "_persist_execution_identity",
        crash_after_confirmation,
    )
    with pytest.raises(
        _InjectedManagedLaunchCrash,
        match="before result",
    ):
        env.process.execute(
            env.access,
            env.attempt,
            request,
            idempotency_key="crash-after-confirmed-execution",
        )

    call_ref = _only_managed_call_ref(env)
    recovered = env.process.get_result(env.access, call_ref)
    replay = env.process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="crash-after-confirmed-execution",
    )
    assert len(confirmed_identities) == 1
    exact_identity = confirmed_identities[0]
    assert env.process._prepared_identity_for_call(call_ref) == exact_identity
    assert env.process._execution_identity_for_call(call_ref) == exact_identity
    assert recovered.process_identity == exact_identity
    assert marker.read_bytes() == b"target\n"
    assert replay == recovered
    assert recovered.status is ProcessStatus.FAILED
    assert recovered.failure is ProcessFailure.RECOVERY_UNCERTAIN
    assert recovered.termination_method.startswith("RECOVERY_SIGTERM")
    _assert_identity_stopped(env.process, exact_identity)
    assert _managed_process_counts(env.database) == {
        "managed_process_claims": 1,
        "managed_process_launches": 1,
        "managed_process_prepared_executions": 1,
        "managed_process_executions": 1,
        "managed_process_results": 1,
        "managed_process_recovery_heads": 1,
        "managed_process_recovery_events": 1,
        "managed_process_recovery_releases": 0,
    }


def test_t21_prepared_identity_tamper_missing_and_mismatch_fail_readback(
    tmp_path: Path,
) -> None:
    def completed_environment(path: Path, namespace: str) -> tuple[_Environment, ProcessResult]:
        environment = _environment(path, namespace=namespace)
        result = environment.process.execute(
            environment.access,
            environment.attempt,
            _request(environment, argv=("-c", "print('identity-evidence')")),
            idempotency_key="prepared-identity-evidence",
        )
        assert _managed_process_counts(environment.database)[
            "managed_process_prepared_executions"
        ] == 1
        return environment, result

    tampered, tampered_result = completed_environment(
        tmp_path / "tampered",
        "prepared-tampered",
    )
    connection = sqlite3.connect(tampered.database)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="claims are immutable"):
            connection.execute(
                "UPDATE managed_process_claims SET call_id=call_id"
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="prepared identities are immutable"):
            connection.execute(
                "UPDATE managed_process_prepared_executions SET pid=pid"
            )
        connection.rollback()
        connection.execute("DROP TRIGGER managed_process_prepared_no_update")
        connection.execute(
            "UPDATE managed_process_prepared_executions SET record_sha256=? WHERE call_id=?",
            ("0" * 64, tampered_result.tool_call_ref.call_id),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(
        ProcessIntegrityError,
        match="prepared execution identity changed",
    ):
        tampered.process.get_result(
            tampered.access,
            tampered_result.tool_call_ref,
        )

    missing, missing_result = completed_environment(
        tmp_path / "missing",
        "prepared-missing",
    )
    connection = sqlite3.connect(missing.database)
    try:
        connection.execute("DROP TRIGGER managed_process_prepared_no_delete")
        connection.execute(
            "DELETE FROM managed_process_prepared_executions WHERE call_id=?",
            (missing_result.tool_call_ref.call_id,),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(
        ProcessIntegrityError,
        match="launch gate and result classification differ",
    ):
        missing.process.get_result(
            missing.access,
            missing_result.tool_call_ref,
        )

    mismatched, mismatched_result = completed_environment(
        tmp_path / "mismatched",
        "prepared-mismatched",
    )
    connection = sqlite3.connect(mismatched.database)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM managed_process_prepared_executions WHERE call_id=?",
            (mismatched_result.tool_call_ref.call_id,),
        ).fetchone()
        assert row is not None
        forged_execution_id = "pexec_" + "0" * 32
        assert forged_execution_id != row["execution_id"]
        forged_payload = {
            "boot_id": row["boot_id"],
            "executable_device": row["executable_device"],
            "executable_inode": row["executable_inode"],
            "executable_sha256": row["executable_sha256"],
            "execution_id": forged_execution_id,
            "pid": row["pid"],
            "process_group_id": row["process_group_id"],
            "project_ref": mismatched.project_ref.value,
            "start_ticks": row["start_ticks"],
            "started_at": row["started_at"],
            "tool_call_ref": mismatched_result.tool_call_ref.value,
        }
        forged_record = hashlib.sha256(
            json.dumps(
                forged_payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        connection.execute("DROP TRIGGER managed_process_prepared_no_update")
        connection.execute(
            "UPDATE managed_process_prepared_executions "
            "SET execution_id=?,record_sha256=? WHERE call_id=?",
            (
                forged_execution_id,
                forged_record,
                mismatched_result.tool_call_ref.call_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(
        ProcessIntegrityError,
        match="launch gate and result classification differ",
    ):
        mismatched.process.get_result(
            mismatched.access,
            mismatched_result.tool_call_ref,
        )


def test_t22_shebang_executable_requires_explicit_interpreter_and_never_runs(
    tmp_path: Path,
) -> None:
    env = _environment(tmp_path, namespace="explicit-interpreter")
    marker = env.root_path / "implicit-interpreter-ran.txt"
    script = env.root_path / "implicit-interpreter.py"
    script.write_text(
        "#!/usr/bin/python3\n"
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_bytes(b'ran')\n"
    )
    script.chmod(0o700)
    request = _request(env, executable=str(script), argv=())

    with pytest.raises(
        ProcessAuthorityError,
        match="native ELF image.*explicit interpreter",
    ):
        env.process.execute(
            env.access,
            env.attempt,
            request,
            idempotency_key="implicit-interpreter-denied",
        )

    assert not marker.exists()
    recovered = env.process.get_result(
        env.access,
        _only_managed_call_ref(env),
    )
    assert recovered.status is ProcessStatus.FAILED
    assert recovered.failure is ProcessFailure.RECOVERY_UNCERTAIN
    assert recovered.process_identity is None
    assert not marker.exists()


def test_t23_stream_only_descriptor_content_is_exact_read_only_and_replayable(
    tmp_path: Path,
) -> None:
    env = _environment(tmp_path, namespace="memory-descriptor")
    memory = MemoryObjectStorageBackend()
    process = ManagedProcessAdapter(
        env.database,
        memory,
        inherited_environment={"LANG": "C.UTF-8"},
    )
    payload = b"descriptor-from-memory"
    payload_ref = memory.put(payload, media_type="application/octet-stream")
    request = _request(
        env,
        argv=(
            "-c",
            (
                "import fcntl,os,sys; fd=int(sys.argv[1]); data=os.read(fd,4096); "
                "state=b'READ_ONLY' if fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE==os.O_RDONLY "
                "else b'WRITABLE'; "
                "sys.stdout.buffer.write(data+b'|'+state)"
            ),
            "@biella-content-fd:payload",
        ),
        descriptor_content_refs={"payload": payload_ref},
    )

    result = process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="memory-descriptor-read-only",
    )
    restarted = ManagedProcessAdapter(
        env.database,
        memory,
        inherited_environment={"LANG": "C.UTF-8"},
    )

    assert result.status is ProcessStatus.SUCCEEDED
    assert memory.read(result.stdout_ref) == payload + b"|READ_ONLY"
    assert memory.read(payload_ref) == payload
    assert restarted.get_result(env.access, result.tool_call_ref) == result


def test_t24_stream_only_stdin_is_exact_and_replayable(tmp_path: Path) -> None:
    env = _environment(tmp_path, namespace="memory-stdin")
    memory = MemoryObjectStorageBackend()
    process = ManagedProcessAdapter(
        env.database,
        memory,
        inherited_environment={"LANG": "C.UTF-8"},
    )
    stdin_payload = b"stdin-from-memory\n"
    stdin_ref = memory.put(stdin_payload, media_type="application/octet-stream")
    request = _request(
        env,
        argv=("-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"),
        stdin_ref=stdin_ref,
    )

    result = process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="memory-stdin-exact",
    )
    restarted = ManagedProcessAdapter(
        env.database,
        memory,
        inherited_environment={"LANG": "C.UTF-8"},
    )

    assert result.status is ProcessStatus.SUCCEEDED
    assert memory.read(result.stdout_ref) == stdin_payload
    assert restarted.get_result(env.access, result.tool_call_ref) == result


def test_t25_normal_readback_verifies_all_inputs_and_exact_artifact_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _environment(tmp_path, namespace="readback-provenance")
    memory = MemoryObjectStorageBackend()
    process = ManagedProcessAdapter(
        env.database,
        memory,
        inherited_environment={"LANG": "C.UTF-8"},
    )
    stdin_bytes = b"stdin-evidence"
    descriptor_bytes = b"descriptor-evidence"
    stdin_ref = memory.put(stdin_bytes, media_type="application/octet-stream")
    descriptor_ref = memory.put(
        descriptor_bytes,
        media_type="application/octet-stream",
    )
    request = _request(
        env,
        argv=(
            "-c",
            (
                "import os,sys; "
                "sys.stdout.buffer.write(sys.stdin.buffer.read()+os.read(int(sys.argv[1]),4096))"
            ),
            "@biella-content-fd:payload",
        ),
        stdin_ref=stdin_ref,
        descriptor_content_refs={"payload": descriptor_ref},
    )
    result = process.execute(
        env.access,
        env.attempt,
        request,
        idempotency_key="readback-provenance",
    )

    memory.delete_replica(descriptor_ref)
    with pytest.raises(
        ProcessIntegrityError,
        match="ContentRef failed verification",
    ):
        process.get_result(env.access, result.tool_call_ref)
    assert memory.put(
        descriptor_bytes,
        media_type="application/octet-stream",
    ) == descriptor_ref

    artifact = process.artifacts.get_artifact(env.access, result.artifact_ref)
    forged = replace(
        artifact,
        source_content_refs=tuple(
            item
            for item in artifact.source_content_refs
            if item != descriptor_ref
        ),
    )
    original_get_artifact = process.artifacts.get_artifact

    def forged_get_artifact(
        access: ProjectAccess,
        artifact_ref: biella.ArtifactRef,
    ) -> biella.Artifact:
        if artifact_ref == result.artifact_ref:
            return forged
        return original_get_artifact(access, artifact_ref)

    monkeypatch.setattr(process.artifacts, "get_artifact", forged_get_artifact)
    with pytest.raises(
        ProcessIntegrityError,
        match="Artifact provenance changed",
    ):
        process.get_result(env.access, result.tool_call_ref)
