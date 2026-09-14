"""P2-04 replaceable isolated-runtime adapter acceptance tests."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

import biella
import pytest
from biella import (
    ArtifactService,
    CapabilityRef,
    DockerIsolatedRuntimeAdapter,
    FilesystemAdapter,
    FilesystemMode,
    FilesystemObjectStorageBackend,
    FilesystemRoot,
    FilesystemRootRef,
    FilesystemScope,
    GraphRef,
    GraphService,
    IsolatedRuntimeAdapter,
    IsolatedRuntimeAuthorityError,
    IsolatedRuntimeConflictError,
    IsolatedRuntimeContractError,
    IsolatedRuntimeScopeError,
    IsolatedRuntimeSpec,
    Node,
    NodeExecutionAttempt,
    NodeExecutionService,
    NodeRef,
    ProjectAccess,
    ProjectRef,
    ProjectStore,
    RunService,
    RuntimeMount,
    RuntimeNetworkPolicy,
    RuntimeOutput,
    RuntimeResourceLimits,
    RuntimeSecretMount,
    RuntimeStatus,
    TaskRevisionService,
)


IMAGE_REF = "sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce"


def test_t01_public_isolated_runtime_contracts_are_active_exports() -> None:
    expected = {
        "DockerIsolatedRuntimeAdapter",
        "IsolatedRuntimeAdapter",
        "IsolatedRuntimeSpec",
        "RuntimeCollectionReceipt",
        "RuntimeDescriptor",
        "RuntimeExecutionReceipt",
        "RuntimeMount",
        "RuntimeNetworkPolicy",
        "RuntimeOutput",
        "RuntimeReceipt",
        "RuntimeRef",
        "RuntimeResourceLimits",
        "RuntimeSecretMount",
        "RuntimeState",
        "RuntimeStatus",
    }
    assert expected.issubset(set(biella.__all__))


@dataclass(frozen=True)
class _Environment:
    database: Path
    access: ProjectAccess
    project_ref: ProjectRef
    objects: FilesystemObjectStorageBackend
    filesystem: FilesystemAdapter
    runtime: DockerIsolatedRuntimeAdapter
    control_root: FilesystemRoot
    input_root: FilesystemRoot
    output_root: FilesystemRoot
    input_path: Path
    output_path: Path
    attempt: NodeExecutionAttempt


def _environment(tmp_path: Path, *, namespace: str = "isolated-runtime") -> _Environment:
    tmp_path.mkdir(parents=True, exist_ok=True)
    control_path = tmp_path / "control"
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    control_path.mkdir()
    input_path.mkdir()
    output_path.mkdir()
    output_path.chmod(0o777)
    (input_path / "input.txt").write_text("exact isolated input\n", encoding="utf-8")
    database = tmp_path / f"{namespace}.sqlite3"
    registration = ProjectStore(database).create_project(namespace=namespace, display_name=namespace.title())
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    filesystem = FilesystemAdapter(database, objects)
    filesystem_capabilities = filesystem.register_capabilities(registration.access)
    runtime = DockerIsolatedRuntimeAdapter(
        database,
        objects,
        runtime_root=tmp_path / "runtime-control",
    )
    process_capabilities = runtime.process.register_capabilities(registration.access)
    runtime_capabilities = runtime.register_capabilities(registration.access)
    capabilities = tuple(sorted((*filesystem_capabilities, *process_capabilities, *runtime_capabilities)))
    task = TaskRevisionService(database).create_task(
        registration.access,
        project_ref=registration.project.project_ref,
        idempotency_key="isolated-runtime-task",
        task_type="runtime.isolated",
        objective="Verify a replaceable exact isolated runtime",
        required_capabilities=capabilities,
        input_refs=(),
        output_contract={"result": "schema://biella/isolated-runtime-receipt/1"},
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
        owner_ref="controller://isolated-runtime-tests",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(registration.project.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "TOOL",
        capabilities,
        (),
        (),
        {"result": "schema://biella/isolated-runtime-receipt/1"},
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
        owner_ref="executor://isolated-runtime-tests",
        lease_seconds=1800,
        idempotency_key="isolated-runtime-node-lease",
    )
    executions.start_node(registration.access, attempt, idempotency_key="isolated-runtime-node-start")
    control_root = filesystem.register_root(
        registration.access,
        path=control_path,
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_WRITE,
        allow_remove=True,
        idempotency_key="isolated-runtime-control-root",
    )
    input_root = filesystem.register_root(
        registration.access,
        path=input_path,
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_ONLY,
        allow_remove=False,
        idempotency_key="isolated-runtime-input-root",
    )
    output_root = filesystem.register_root(
        registration.access,
        path=output_path,
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_WRITE,
        allow_remove=True,
        idempotency_key="isolated-runtime-output-root",
    )
    return _Environment(
        database,
        registration.access,
        registration.project.project_ref,
        objects,
        filesystem,
        runtime,
        control_root,
        input_root,
        output_root,
        input_path,
        output_path,
        attempt,
    )


def _spec(
    env: _Environment,
    *,
    args: tuple[str, ...],
    outputs: tuple[RuntimeOutput, ...] = (),
    secrets: tuple[RuntimeSecretMount, ...] = (),
    timeout_seconds: float = 10,
    limits: RuntimeResourceLimits = RuntimeResourceLimits(cpus=0.5, memory_bytes=64 * 1024 * 1024, process_count=32),
    network_policy: RuntimeNetworkPolicy = RuntimeNetworkPolicy.NONE,
) -> IsolatedRuntimeSpec:
    return IsolatedRuntimeSpec(
        env.project_ref,
        IMAGE_REF,
        "/bin/sh",
        args,
        "/workspace",
        (
            RuntimeMount(env.input_root.root_ref, ".", "/workspace/input", True),
            RuntimeMount(env.output_root.root_ref, ".", "/workspace/output", False),
        ),
        outputs,
        secrets,
        network_policy,
        limits,
        {"BIELLA_TEST_MODE": "exact"},
        timeout_seconds,
        1024 * 1024,
        1024 * 1024,
    )


def test_t02_registers_contract_and_real_descriptor(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    implementations = env.runtime.register_capabilities(env.access)
    assert set(implementations) == {
        CapabilityRef(f"runtime.{operation}", "1.0.0")
        for operation in ("create", "start", "execute", "cancel", "stop", "inspect", "collect", "cleanup", "describe")
    }
    assert isinstance(env.runtime, IsolatedRuntimeAdapter)
    descriptor = env.runtime.describe_runtime(
        env.access,
        env.attempt,
        control_root_ref=env.control_root.root_ref,
        idempotency_key="describe-real-runtime",
    )
    assert descriptor.adapter_kind == "oci.container.cli"
    installed_runtime_version = subprocess.check_output(
        ["docker", "version", "--format", "{{.Client.Version}}"], text=True, timeout=10
    ).strip()
    assert descriptor.runtime_version == installed_runtime_version
    assert descriptor.supported_network_policies == (RuntimeNetworkPolicy.NONE,)
    assert descriptor.enforced_limit_kinds == ("cpu", "memory", "process")
    assert descriptor.unsupported_limit_kinds == ("gpu", "restricted_network", "storage")
    assert descriptor.gpu_count == 0
    assert len(descriptor.executable_digest) == 64


def test_t03_exact_image_scope_mount_and_compatibility_fail_closed(tmp_path: Path) -> None:
    env = _environment(tmp_path / "alpha", namespace="runtime-alpha")
    with pytest.raises(IsolatedRuntimeContractError, match="immutable sha256"):
        IsolatedRuntimeSpec(env.project_ref, "alpine:3.22", "/bin/true")
    beta = ProjectStore(env.database).create_project(namespace="runtime-beta", display_name="Runtime Beta")
    with pytest.raises(IsolatedRuntimeScopeError):
        IsolatedRuntimeSpec(
            env.project_ref,
            IMAGE_REF,
            "/bin/true",
            mounts=(RuntimeMount(FilesystemRootRef(beta.project.project_ref, env.input_root.root_ref.root_id), ".", "/inputs", True),),
        )
    restricted = _spec(
        env,
        args=("-c", "exit 0"),
        network_policy=RuntimeNetworkPolicy.RESTRICTED,
    )
    with pytest.raises(IsolatedRuntimeContractError, match="cannot enforce"):
        env.runtime.create(
            env.access,
            env.attempt,
            restricted,
            control_root_ref=env.control_root.root_ref,
            idempotency_key="reject-restricted-network",
        )
    storage = _spec(
        env,
        args=("-c", "exit 0"),
        limits=RuntimeResourceLimits(storage_bytes=1024 * 1024),
    )
    with pytest.raises(IsolatedRuntimeContractError, match="storage quota"):
        env.runtime.create(
            env.access,
            env.attempt,
            storage,
            control_root_ref=env.control_root.root_ref,
            idempotency_key="reject-storage-limit",
        )
    gpu = _spec(env, args=("-c", "exit 0"), limits=RuntimeResourceLimits(gpu_count=1))
    with pytest.raises(IsolatedRuntimeContractError, match="GPU visibility"):
        env.runtime.create(
            env.access,
            env.attempt,
            gpu,
            control_root_ref=env.control_root.root_ref,
            idempotency_key="reject-unavailable-gpu",
        )
    host_root = env.filesystem.register_root(
        env.access,
        path="/",
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_ONLY,
        allow_remove=False,
        idempotency_key="forbidden-host-root",
    )
    forbidden = IsolatedRuntimeSpec(
        env.project_ref,
        IMAGE_REF,
        "/bin/true",
        mounts=(RuntimeMount(host_root.root_ref, ".", "/host", True),),
    )
    with pytest.raises(IsolatedRuntimeAuthorityError, match="forbidden host path"):
        env.runtime.create(
            env.access,
            env.attempt,
            forbidden,
            control_root_ref=env.control_root.root_ref,
            idempotency_key="reject-host-root-mount",
        )


def test_t04_real_isolated_execute_collect_before_cleanup_and_secret_inertness(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    secret = "runtime-secret-value-that-must-never-persist"
    secret_ref = "secret://runtime/api-token"
    spec = _spec(
        env,
        args=(
            "-c",
            "test -r /workspace/input/input.txt && test ! -w /workspace/input/input.txt && test -s /run/secrets/api-token && cat /workspace/input/input.txt > /workspace/output/result.txt && ls /sys/class/net > /workspace/output/network.txt && printf 'secret-present\\n' && printf 'stderr-marker\\n' >&2",
        ),
        outputs=(
            RuntimeOutput(env.output_root.root_ref, "result.txt", "text/plain"),
            RuntimeOutput(env.output_root.root_ref, "network.txt", "text/plain"),
        ),
        secrets=(RuntimeSecretMount(secret_ref, "/run/secrets/api-token"),),
    )
    created = env.runtime.create(
        env.access,
        env.attempt,
        spec,
        control_root_ref=env.control_root.root_ref,
        idempotency_key="real-runtime-create",
    )
    assert created.state.status is RuntimeStatus.CREATED
    assert created.state.image_id == IMAGE_REF
    assert env.runtime.create(
        env.access,
        env.attempt,
        spec,
        control_root_ref=env.control_root.root_ref,
        idempotency_key="real-runtime-create",
    ) == created
    started = env.runtime.start(
        env.access,
        env.attempt,
        created.state.runtime_ref,
        secret_values={secret_ref: secret},
        idempotency_key="real-runtime-start",
    )
    assert started.state.container_id is not None
    assert started.state.enforced_limits["network_mode"] == "none"
    assert started.state.enforced_limits["nano_cpus"] == 500_000_000
    assert started.state.enforced_limits["memory_bytes"] == 64 * 1024 * 1024
    assert started.state.enforced_limits["pids_limit"] == 32
    assert started.state.enforced_limits["readonly_rootfs"] is True
    assert started.state.observed_limits["configured_nano_cpus"] == 500_000_000
    assert started.state.observed_limits["configured_memory_bytes"] == 64 * 1024 * 1024
    assert started.state.observed_limits["configured_pids_limit"] == 32
    assert started.state.observed_limits["configured_network_mode"] == "none"
    inspected = env.runtime.inspect(
        env.access,
        env.attempt,
        started.state.runtime_ref,
        idempotency_key="real-runtime-inspect",
    )
    assert inspected.state == started.state
    assert env.runtime.inspect(
        env.access,
        env.attempt,
        started.state.runtime_ref,
        idempotency_key="real-runtime-inspect",
    ) == inspected
    execution = env.runtime.execute(
        env.access,
        env.attempt,
        started.state.runtime_ref,
        secret_values={secret_ref: secret},
        idempotency_key="real-runtime-execute",
    )
    assert execution.state.status is RuntimeStatus.SUCCEEDED
    assert execution.stdout_ref is not None
    assert execution.stderr_ref is not None
    assert env.objects.read(execution.stdout_ref) == b"secret-present\n"
    assert env.objects.read(execution.stderr_ref) == b"stderr-marker\n"
    with pytest.raises(IsolatedRuntimeConflictError, match="required outputs"):
        env.runtime.cleanup(
            env.access,
            env.attempt,
            execution.state.runtime_ref,
            idempotency_key="real-runtime-premature-cleanup",
        )
    collection = env.runtime.collect_outputs(
        env.access,
        env.attempt,
        execution.state.runtime_ref,
        secret_values={secret_ref: secret},
        idempotency_key="real-runtime-collect",
    )
    assert collection.state.status is RuntimeStatus.OUTPUTS_COLLECTED
    assert len(collection.output_artifact_refs) == 2
    artifacts = ArtifactService(env.database)
    contents = tuple(
        artifacts.get_artifact(env.access, artifact_ref).content_ref
        for artifact_ref in collection.output_artifact_refs
    )
    assert contents[0] is not None and env.objects.read(contents[0]) == b"exact isolated input\n"
    assert contents[1] is not None and env.objects.read(contents[1]) == b"lo\n"
    container_id = collection.state.container_id
    cleanup = env.runtime.cleanup(
        env.access,
        env.attempt,
        collection.state.runtime_ref,
        idempotency_key="real-runtime-cleanup",
    )
    assert cleanup.state.status is RuntimeStatus.CLEANED
    assert contents[0] is not None and env.objects.read(contents[0]) == b"exact isolated input\n"
    missing = subprocess.run(
        ("/usr/bin/docker", "container", "inspect", str(container_id)),
        check=False,
        capture_output=True,
    )
    assert missing.returncode != 0
    assert secret.encode() not in env.database.read_bytes()
    for content_path in (tmp_path / "objects" / "objects" / "sha256").rglob("content"):
        assert secret.encode() not in content_path.read_bytes()


def test_t05_read_only_mount_and_direct_argv_hostile_text_are_inert(tmp_path: Path) -> None:
    readonly = _environment(tmp_path / "readonly", namespace="runtime-readonly")
    original = (readonly.input_path / "input.txt").read_bytes()
    write_spec = _spec(
        readonly,
        args=("-c", "printf changed > /workspace/input/input.txt"),
        outputs=(),
        secrets=(),
    )
    created = readonly.runtime.create(
        readonly.access,
        readonly.attempt,
        write_spec,
        control_root_ref=readonly.control_root.root_ref,
        idempotency_key="readonly-create",
    )
    started = readonly.runtime.start(
        readonly.access,
        readonly.attempt,
        created.state.runtime_ref,
        secret_values={},
        idempotency_key="readonly-start",
    )
    executed = readonly.runtime.execute(
        readonly.access,
        readonly.attempt,
        started.state.runtime_ref,
        secret_values={},
        idempotency_key="readonly-execute",
    )
    assert executed.state.status is RuntimeStatus.FAILED
    assert (readonly.input_path / "input.txt").read_bytes() == original
    readonly.runtime.cleanup(
        readonly.access,
        readonly.attempt,
        executed.state.runtime_ref,
        idempotency_key="readonly-cleanup",
    )

    hostile = _environment(tmp_path / "hostile", namespace="runtime-hostile")
    marker = hostile.output_path / "hostile-created"
    hostile_spec = IsolatedRuntimeSpec(
        hostile.project_ref,
        IMAGE_REF,
        "/bin/echo",
        ("$(touch /workspace/output/hostile-created)", ";", "hostile instruction"),
        "/workspace",
        (RuntimeMount(hostile.output_root.root_ref, ".", "/workspace/output", False),),
        (),
        (),
        RuntimeNetworkPolicy.NONE,
        RuntimeResourceLimits(process_count=16),
    )
    hostile_created = hostile.runtime.create(
        hostile.access,
        hostile.attempt,
        hostile_spec,
        control_root_ref=hostile.control_root.root_ref,
        idempotency_key="hostile-create",
    )
    hostile_started = hostile.runtime.start(
        hostile.access,
        hostile.attempt,
        hostile_created.state.runtime_ref,
        secret_values={},
        idempotency_key="hostile-start",
    )
    hostile_execution = hostile.runtime.execute(
        hostile.access,
        hostile.attempt,
        hostile_started.state.runtime_ref,
        secret_values={},
        idempotency_key="hostile-execute",
    )
    assert hostile_execution.stdout_ref is not None
    assert b"$(touch /workspace/output/hostile-created) ; hostile instruction" in hostile.objects.read(
        hostile_execution.stdout_ref
    )
    assert not marker.exists()
    hostile.runtime.cleanup(
        hostile.access,
        hostile.attempt,
        hostile_execution.state.runtime_ref,
        idempotency_key="hostile-cleanup",
    )


def test_t06_timeout_cancel_stop_and_crash_release_only_owned_containers(tmp_path: Path) -> None:
    timeout_env = _environment(tmp_path / "timeout", namespace="runtime-timeout")
    timeout_spec = _spec(
        timeout_env,
        args=("-c", "sleep 30"),
        timeout_seconds=0.5,
        limits=RuntimeResourceLimits(memory_bytes=32 * 1024 * 1024, process_count=16),
    )
    timeout_created = timeout_env.runtime.create(
        timeout_env.access,
        timeout_env.attempt,
        timeout_spec,
        control_root_ref=timeout_env.control_root.root_ref,
        idempotency_key="timeout-create",
    )
    timeout_started = timeout_env.runtime.start(
        timeout_env.access,
        timeout_env.attempt,
        timeout_created.state.runtime_ref,
        secret_values={},
        idempotency_key="timeout-start",
    )
    assert timeout_started.state.status is RuntimeStatus.RUNNING
    timeout_execution = timeout_env.runtime.execute(
        timeout_env.access,
        timeout_env.attempt,
        timeout_started.state.runtime_ref,
        secret_values={},
        idempotency_key="timeout-execute",
    )
    assert timeout_execution.state.status is RuntimeStatus.TIMED_OUT
    assert timeout_execution.state.failure == "TIMEOUT"
    assert timeout_env.runtime.execute(
        timeout_env.access,
        timeout_env.attempt,
        timeout_started.state.runtime_ref,
        secret_values={},
        idempotency_key="timeout-execute",
    ) == timeout_execution
    timeout_env.runtime.cleanup(
        timeout_env.access,
        timeout_env.attempt,
        timeout_execution.state.runtime_ref,
        idempotency_key="timeout-cleanup",
    )

    cancel_env = _environment(tmp_path / "cancel", namespace="runtime-cancel")
    cancel_spec = _spec(cancel_env, args=("-c", "sleep 30"), timeout_seconds=60)
    cancel_created = cancel_env.runtime.create(
        cancel_env.access,
        cancel_env.attempt,
        cancel_spec,
        control_root_ref=cancel_env.control_root.root_ref,
        idempotency_key="cancel-create",
    )
    cancel_started = cancel_env.runtime.start(
        cancel_env.access,
        cancel_env.attempt,
        cancel_created.state.runtime_ref,
        secret_values={},
        idempotency_key="cancel-start",
    )
    cancelled = cancel_env.runtime.cancel(
        cancel_env.access,
        cancel_env.attempt,
        cancel_started.state.runtime_ref,
        idempotency_key="cancel-running",
    )
    assert cancelled.state.status is RuntimeStatus.CANCELLED
    cancel_env.runtime.cleanup(
        cancel_env.access,
        cancel_env.attempt,
        cancelled.state.runtime_ref,
        idempotency_key="cancel-cleanup",
    )

    stop_env = _environment(tmp_path / "stop", namespace="runtime-stop")
    stop_spec = _spec(stop_env, args=("-c", "sleep 30"), timeout_seconds=60)
    stop_created = stop_env.runtime.create(
        stop_env.access,
        stop_env.attempt,
        stop_spec,
        control_root_ref=stop_env.control_root.root_ref,
        idempotency_key="stop-create",
    )
    stop_started = stop_env.runtime.start(
        stop_env.access,
        stop_env.attempt,
        stop_created.state.runtime_ref,
        secret_values={},
        idempotency_key="stop-start",
    )
    stopped = stop_env.runtime.stop(
        stop_env.access,
        stop_env.attempt,
        stop_started.state.runtime_ref,
        idempotency_key="stop-running",
    )
    assert stopped.state.status is RuntimeStatus.STOPPED
    stop_env.runtime.cleanup(
        stop_env.access,
        stop_env.attempt,
        stopped.state.runtime_ref,
        idempotency_key="stop-cleanup",
    )

    crash_env = _environment(tmp_path / "crash", namespace="runtime-crash")
    crash_spec = _spec(crash_env, args=("-c", "printf crash >&2; exit 7"))
    crash_created = crash_env.runtime.create(
        crash_env.access,
        crash_env.attempt,
        crash_spec,
        control_root_ref=crash_env.control_root.root_ref,
        idempotency_key="crash-create",
    )
    crash_started = crash_env.runtime.start(
        crash_env.access,
        crash_env.attempt,
        crash_created.state.runtime_ref,
        secret_values={},
        idempotency_key="crash-start",
    )
    crashed = crash_env.runtime.execute(
        crash_env.access,
        crash_env.attempt,
        crash_started.state.runtime_ref,
        secret_values={},
        idempotency_key="crash-execute",
    )
    assert crashed.state.status is RuntimeStatus.FAILED
    assert crashed.state.exit_code == 7
    assert crashed.stderr_ref is not None and crash_env.objects.read(crashed.stderr_ref) == b"crash"
    crash_env.runtime.cleanup(
        crash_env.access,
        crash_env.attempt,
        crashed.state.runtime_ref,
        idempotency_key="crash-cleanup",
    )


def test_t07_restart_reconciles_owned_runtime_and_never_kills_unknown(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    spec = _spec(env, args=("-c", "sleep 30"), timeout_seconds=60)
    created = env.runtime.create(
        env.access,
        env.attempt,
        spec,
        control_root_ref=env.control_root.root_ref,
        idempotency_key="orphan-create",
    )
    started = env.runtime.start(
        env.access,
        env.attempt,
        created.state.runtime_ref,
        secret_values={},
        idempotency_key="orphan-start",
    )
    unknown = subprocess.run(
        (
            "/usr/bin/docker",
            "container",
            "create",
            "--label",
            f"biella.project={env.project_ref.value}",
            "--label",
            "biella.runtime=rt_ffffffffffffffffffffffffffffffff",
            "--network",
            "none",
            IMAGE_REF,
            "/bin/sleep",
            "30",
        ),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(("/usr/bin/docker", "container", "start", unknown), check=True, capture_output=True)
    try:
        restarted = DockerIsolatedRuntimeAdapter(
            env.database,
            FilesystemObjectStorageBackend(tmp_path / "objects"),
            runtime_root=tmp_path / "runtime-control",
        )
        assert restarted.get_receipt(env.access, started.tool_call_ref) == started
        reconciliation = restarted.reconcile_orphans(
            env.access,
            env.attempt,
            control_root_ref=env.control_root.root_ref,
            idempotency_key="restart-orphan-reconciliation",
        )
        assert reconciliation.recovered == (started.state.runtime_ref,)
        assert reconciliation.cleaned == ()
        assert unknown in reconciliation.unknown_container_ids
        unknown_state = subprocess.run(
            ("/usr/bin/docker", "container", "inspect", "--format", "{{.State.Running}}", unknown),
            check=True,
            capture_output=True,
            text=True,
        )
        assert unknown_state.stdout.strip() == "true"
        cancelled = restarted.cancel(
            env.access,
            env.attempt,
            started.state.runtime_ref,
            idempotency_key="recovered-cancel",
        )
        restarted.cleanup(
            env.access,
            env.attempt,
            cancelled.state.runtime_ref,
            idempotency_key="recovered-cleanup",
        )
    finally:
        subprocess.run(("/usr/bin/docker", "container", "rm", "--force", unknown), check=False, capture_output=True)


def test_t08_stale_generation_project_scope_and_receipt_tamper_fail_closed(tmp_path: Path) -> None:
    env = _environment(tmp_path / "stale", namespace="runtime-stale")
    spec = _spec(env, args=("-c", "exit 0"))
    created = env.runtime.create(
        env.access,
        env.attempt,
        spec,
        control_root_ref=env.control_root.root_ref,
        idempotency_key="stale-create",
    )
    started = env.runtime.start(
        env.access,
        env.attempt,
        created.state.runtime_ref,
        secret_values={},
        idempotency_key="stale-start",
    )
    execution = env.runtime.execute(
        env.access,
        env.attempt,
        started.state.runtime_ref,
        secret_values={},
        idempotency_key="stale-execute",
    )
    with pytest.raises(IsolatedRuntimeConflictError, match="stale"):
        env.runtime.get_state(env.access, started.state.runtime_ref)
    with pytest.raises(IsolatedRuntimeConflictError, match="stale"):
        env.runtime.collect_outputs(
            env.access,
            env.attempt,
            started.state.runtime_ref,
            secret_values={},
            idempotency_key="stale-output-collection",
        )
    beta = ProjectStore(env.database).create_project(namespace="runtime-scope-beta", display_name="Runtime Scope Beta")
    with pytest.raises(IsolatedRuntimeScopeError):
        env.runtime.get_state(beta.access, execution.state.runtime_ref)
    env.runtime.cleanup(
        env.access,
        env.attempt,
        execution.state.runtime_ref,
        idempotency_key="stale-cleanup",
    )

    tamper = _environment(tmp_path / "tamper", namespace="runtime-tamper")
    tampered = tamper.runtime.create(
        tamper.access,
        tamper.attempt,
        _spec(tamper, args=("-c", "exit 0")),
        control_root_ref=tamper.control_root.root_ref,
        idempotency_key="tamper-create",
    )
    forged = biella.RuntimeReceipt(
        tampered.operation,
        tampered.state,
        (),
        tampered.stdout_ref,
        tampered.stderr_ref,
        tampered.output_artifact_refs,
        tampered.tool_call_ref,
        tampered.artifact_ref,
        tampered.completed_at,
    )
    with sqlite3.connect(tamper.database) as connection:
        connection.execute("DROP TRIGGER isolated_runtime_results_no_update")
        connection.execute(
            "UPDATE isolated_runtime_operation_results SET receipt_json=?,record_sha256=? WHERE project_id=? AND call_id=?",
            (
                json.dumps(forged.payload(), sort_keys=True, separators=(",", ":")),
                forged.record_sha256,
                tamper.project_ref.value,
                tampered.tool_call_ref.call_id,
            ),
        )
    with pytest.raises(biella.IsolatedRuntimeIntegrityError, match="Artifact manifest differ"):
        tamper.runtime.get_receipt(tamper.access, tampered.tool_call_ref)


def test_t09_kernel_contracts_have_no_provider_runtime_types(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    spec = _spec(env, args=("-c", "exit 0"))
    payload = json.dumps(spec.payload(), sort_keys=True)
    for provider_type in ("Docker", "Podman", "Kubernetes", "containerd"):
        assert provider_type not in payload
        assert provider_type not in (Path(__file__).parents[1] / "src/biella/task.py").read_text(encoding="utf-8")
        assert provider_type not in (Path(__file__).parents[1] / "src/biella/graph.py").read_text(encoding="utf-8")


def test_t10_state_and_content_erasure_are_detected(tmp_path: Path) -> None:
    tamper = _environment(tmp_path / "state", namespace="runtime-state-tamper")
    created = tamper.runtime.create(
        tamper.access,
        tamper.attempt,
        _spec(tamper, args=("-c", "exit 0")),
        control_root_ref=tamper.control_root.root_ref,
        idempotency_key="state-tamper-create",
    )
    with sqlite3.connect(tamper.database) as connection:
        state_json = connection.execute(
            "SELECT state_json FROM isolated_runtime_states WHERE project_id=? AND runtime_id=? AND generation=?",
            (
                tamper.project_ref.value,
                created.state.runtime_ref.runtime_id,
                created.state.runtime_ref.generation,
            ),
        ).fetchone()
        assert state_json is not None
        payload = json.loads(state_json[0])
        payload["runtime_version"] = "tampered-runtime-version"
        connection.execute("DROP TRIGGER isolated_runtime_states_no_update")
        connection.execute(
            "UPDATE isolated_runtime_states SET state_json=? WHERE project_id=? AND runtime_id=? AND generation=?",
            (
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                tamper.project_ref.value,
                created.state.runtime_ref.runtime_id,
                created.state.runtime_ref.generation,
            ),
        )
    with pytest.raises(biella.IsolatedRuntimeIntegrityError, match="state evidence changed"):
        tamper.runtime.get_state(tamper.access, created.state.runtime_ref)

    erased = _environment(tmp_path / "erased", namespace="runtime-content-erased")
    erased_created = erased.runtime.create(
        erased.access,
        erased.attempt,
        _spec(erased, args=("-c", "printf 'runtime content evidence\\n'")),
        control_root_ref=erased.control_root.root_ref,
        idempotency_key="erased-create",
    )
    erased_started = erased.runtime.start(
        erased.access,
        erased.attempt,
        erased_created.state.runtime_ref,
        secret_values={},
        idempotency_key="erased-start",
    )
    erased_execution = erased.runtime.execute(
        erased.access,
        erased.attempt,
        erased_started.state.runtime_ref,
        secret_values={},
        idempotency_key="erased-execute",
    )
    assert erased_execution.stdout_ref is not None
    erased.runtime.cleanup(
        erased.access,
        erased.attempt,
        erased_execution.state.runtime_ref,
        idempotency_key="erased-cleanup",
    )
    digest = erased_execution.stdout_ref.digest
    content_path = tmp_path / "erased" / "objects" / "objects" / "sha256" / digest[:2] / digest[2:4] / digest / "content"
    content_path.unlink()
    with pytest.raises(biella.IsolatedRuntimeIntegrityError, match="ContentRef failed verification"):
        erased.runtime.get_receipt(erased.access, erased_execution.tool_call_ref)


def test_t15_type_build_exact_wheel_and_separate_installed_restart() -> None:
    root = Path(__file__).resolve().parents[1]
    source_paths = (
        root / "src/biella/__init__.py",
        root / "src/biella/isolated_runtime.py",
        root / "tests/test_p2_04_isolated_runtime.py",
        root / "tests/fixtures/p2_04_installed_writer.py",
        root / "tests/fixtures/p2_04_installed_reader.py",
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
        for path in sorted((root / "src/biella").glob("*.py"))
        if path.name != "migration.py"
    )
    assert "QuarantineRef" not in active_runtime
    typecheck = subprocess.run(
        (sys.executable, "-m", "mypy", "--strict", "src"),
        cwd=root,
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
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert build.returncode == 0, f"{build.stdout}\n{build.stderr}"
        wheels = tuple(wheel_root.glob("biella_engine-*.whl"))
        assert len(wheels) == 1
        wheel = wheels[0]
        package_paths = tuple(sorted((root / "src/biella").glob("*.py")))
        with zipfile.ZipFile(wheel) as archive:
            wheel_names = {
                name
                for name in archive.namelist()
                if name.startswith("biella/") and name.endswith(".py")
            }
            assert wheel_names == {f"biella/{path.name}" for path in package_paths}
            for path in package_paths:
                assert hashlib.sha256(archive.read(f"biella/{path.name}")).hexdigest() == hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
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
        environment = os.environ.copy()
        environment.update(
            {
                "BIELLA_CONTROL_ROOT": str(temporary / "control"),
                "BIELLA_DATABASE": str(temporary / "restart.sqlite3"),
                "BIELLA_OBJECT_ROOT": str(temporary / "objects"),
                "BIELLA_OUTPUT_ROOT": str(temporary / "output"),
                "BIELLA_RUNTIME_ROOT": str(temporary / "runtime"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(installed),
            }
        )
        writer = subprocess.run(
            (sys.executable, str(root / "tests/fixtures/p2_04_installed_writer.py")),
            cwd=temporary,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert writer.returncode == 0, f"{writer.stdout}\n{writer.stderr}"
        identity = json.loads(writer.stdout)
        environment["BIELLA_EXPECTED"] = json.dumps(identity, sort_keys=True)
        reader = subprocess.run(
            (sys.executable, str(root / "tests/fixtures/p2_04_installed_reader.py")),
            cwd=temporary,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert reader.returncode == 0, f"{reader.stdout}\n{reader.stderr}"
        observed = json.loads(reader.stdout)
        assert observed["cleanup_record_sha256"] == identity["cleanup_record_sha256"]
        assert observed["collection_record_sha256"] == identity["collection_record_sha256"]
        assert observed["output_artifact_ref"] == identity["output_artifact_ref"]
        assert observed["status"] == RuntimeStatus.CLEANED.value
