"""P1-07 dynamic runtime resource inventory acceptance tests."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

import pytest

from biella import (
    ArtifactService,
    Capability,
    CapabilityRef,
    CapabilityRegistry,
    ContentRef,
    FakeResourceObserver,
    LocalResourceObserver,
    ProjectAccess,
    ProjectStore,
    QuantitySource,
    Resource,
    ResourceArtifactLocality,
    ResourceContractError,
    ResourceDeviceSnapshot,
    ResourceFit,
    ResourceFitRequest,
    ResourceHealth,
    ResourceIntegrityError,
    ResourceLocality,
    ResourceObservation,
    ResourceObserver,
    ResourceQuantity,
    ResourceScopeError,
    ResourceService,
    ResourceSnapshot,
    ResourceStaleError,
    ResourceWorkspaceLocality,
    evaluateResourceFit,
)


ROOT = Path(__file__).resolve().parents[1]
BASE = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def _time(seconds: int) -> str:
    return (BASE + timedelta(seconds=seconds)).isoformat(timespec="microseconds")


def _measured(value: int | float, unit: str = "bytes") -> ResourceQuantity:
    return ResourceQuantity.measured(value, unit, "test://sensor/current")


def _derived(value: int | float, unit: str = "bytes") -> ResourceQuantity:
    return ResourceQuantity.derived(value, unit, "test://derived/current")


def _observation(
    second: int,
    *,
    health: ResourceHealth = ResourceHealth.HEALTHY,
    physical_memory: int = 64,
    effective_memory: int = 32,
    used_memory: int = 8,
    available_memory: int = 24,
    devices: tuple[ResourceDeviceSnapshot, ...] = (),
    locality: ResourceLocality | None = None,
    runtime_attributes: dict[str, str] | None = None,
    pressure: dict[str, ResourceQuantity] | None = None,
    fresh_for_seconds: int = 60,
) -> ResourceObservation:
    return ResourceObservation(
        observed_at=_time(second),
        fresh_for_seconds=fresh_for_seconds,
        health=health,
        physical_capacity={
            "cpu.logical_count": _measured(16, "count"),
            "memory.bytes": _measured(physical_memory),
        },
        effective_capacity={
            "cpu.logical_count": _derived(8, "count"),
            "memory.bytes": _derived(effective_memory),
        },
        used_capacity={"memory.bytes": _measured(used_memory)},
        available_capacity={
            "cpu.logical_count": _derived(6, "count"),
            "memory.bytes": _derived(available_memory),
            "network.bandwidth_bps": ResourceQuantity.unknown(
                "bytes_per_second", "test://network/not-measured"
            ),
        },
        pressure={} if pressure is None else pressure,
        devices=devices,
        locality=ResourceLocality() if locality is None else locality,
        runtime_attributes=(
            {"runtime.kind": "test.reference"}
            if runtime_attributes is None
            else runtime_attributes
        ),
        known_cost=ResourceQuantity.unknown(
            "usd_per_hour", "test://cost/not-measured"
        ),
    )


def _inventory(
    root: Path,
    *,
    namespace: str = "resource-alpha",
) -> tuple[ResourceService, ProjectAccess, Resource]:
    database = root / f"{namespace}.sqlite3"
    projects = ProjectStore(database)
    registration = projects.create_project(
        namespace=namespace,
        display_name=namespace,
    )
    resource = Resource.create(
        registration.project.project_ref,
        resource_kind="runtime.host",
        locality_ref=f"host://{namespace}",
        configured_capacity={
            "memory.bytes": ResourceQuantity.configured(
                128, "bytes", "config://resource/expected"
            )
        },
        static_attributes={"runtime.class": "linux"},
        ownership_metadata={"owner.kind": "project"},
    )
    service = ResourceService(database)
    service.register_resource(registration.access, resource)
    return service, registration.access, resource


def test_t01_required_interfaces_are_public_provider_neutral_and_exact(tmp_path: Path) -> None:
    assert Resource is not None
    assert ResourceSnapshot is not None
    assert ResourceObserver is not None
    assert evaluateResourceFit is not None
    assert {item.value for item in ResourceFit} == {
        "FIT",
        "FIT_REDUCED",
        "REQUIRES_OTHER_RESOURCE",
        "TEMPORARILY_UNAVAILABLE",
        "UNKNOWN",
    }
    service, access, resource = _inventory(tmp_path)
    stored = service.get_resource(access, resource.resource_ref)
    assert stored == resource
    assert stored.resource_ref.value.startswith("resource://prj_")
    snapshot = service.observe_resource(
        access,
        resource.resource_ref,
        FakeResourceObserver((_observation(0),)),
    )
    assert snapshot.resource_record_sha256 == resource.record_sha256
    assert service.get_snapshot(access, snapshot.snapshot_ref) == snapshot
    assert snapshot.snapshot_ref.value.startswith("resource-snapshot://prj_")
    other = ProjectStore(service.database_path).create_project(
        namespace="resource-beta",
        display_name="Resource Beta",
    )
    with pytest.raises(ResourceScopeError):
        service.get_resource(other.access, resource.resource_ref)


def test_t02_local_observer_reports_real_current_values_and_unknowns(tmp_path: Path) -> None:
    _, _, resource = _inventory(tmp_path)
    observation = LocalResourceObserver(
        fresh_for_seconds=30,
        expected_locality_ref=resource.locality_ref,
    ).observe(resource)
    logical = observation.physical_capacity["cpu.logical_count"]
    memory = observation.physical_capacity["memory.bytes"]
    storage = observation.physical_capacity["storage.workspace.bytes"]
    assert logical.source_kind is QuantitySource.MEASURED
    assert logical.value == os.cpu_count()
    assert isinstance(memory.value, int) and memory.value > 0
    assert isinstance(storage.value, int) and storage.value > 0
    assert observation.effective_capacity["memory.bytes"].value is not None
    assert float(observation.effective_capacity["memory.bytes"].value) <= float(memory.value)
    assert observation.runtime_attributes["runtime.os"]
    assert observation.runtime_attributes["runtime.kernel"]
    bandwidth = observation.available_capacity["network.bandwidth_bps"]
    assert bandwidth.value is None
    assert bandwidth.source_kind is QuantitySource.UNKNOWN
    assert observation.locality.observed_dimensions == ()
    with pytest.raises(ResourceScopeError):
        LocalResourceObserver(
            expected_locality_ref="host://different-runtime"
        ).observe(resource)
    for capacity in (
        observation.physical_capacity,
        observation.effective_capacity,
        observation.used_capacity,
        observation.available_capacity,
    ):
        assert all(
            quantity.source_kind is not QuantitySource.CONFIGURED
            for quantity in capacity.values()
        )


def test_t03_cpu_only_and_no_gpu_is_a_valid_observation(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    snapshot = service.observe_resource(
        access, resource.resource_ref, FakeResourceObserver((_observation(0, devices=()),))
    )
    assert snapshot.devices == ()
    assert snapshot.physical_capacity["cpu.logical_count"].value == 16
    assert evaluateResourceFit(
        snapshot,
        ResourceFitRequest(required_available={"cpu.logical_count": 2}),
        at=_time(1),
    ).classification is ResourceFit.FIT


def test_t04_arbitrary_gpu_vendor_and_features_are_not_schema_locked(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    accelerator = ResourceDeviceSnapshot(
        device_id="fabric:orbital-7",
        device_kind="gpu",
        vendor="Acme Quantum Graphics",
        model="QG-42",
        features=("matrix.v9", "shared-memory"),
        health=ResourceHealth.HEALTHY,
        physical_capacity={"vram.bytes": _measured(96)},
        effective_capacity={"vram.bytes": _derived(80)},
        used_capacity={"vram.bytes": _measured(16)},
        available_capacity={"vram.bytes": _derived(64)},
    )
    snapshot = service.observe_resource(
        access,
        resource.resource_ref,
        FakeResourceObserver((_observation(0, devices=(accelerator,)),)),
    )
    assert snapshot.devices[0].vendor == "Acme Quantum Graphics"
    assert snapshot.devices[0].features == ("matrix.v9", "shared-memory")
    assert evaluateResourceFit(
        snapshot,
        ResourceFitRequest(
            required_device_kind="gpu", required_device_features=("matrix.v9",)
        ),
        at=_time(1),
    ).classification is ResourceFit.FIT


def test_t05_multiple_heterogeneous_gpus_preserve_device_truth(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    devices = (
        ResourceDeviceSnapshot(
            device_id="pci:0000:01:00.0",
            device_kind="gpu",
            vendor="vendor-a",
            model="a1",
            health=ResourceHealth.HEALTHY,
            physical_capacity={"vram.bytes": _measured(80)},
            effective_capacity={"vram.bytes": _derived(80)},
            used_capacity={"vram.bytes": _measured(20)},
            available_capacity={"vram.bytes": _derived(60)},
        ),
        ResourceDeviceSnapshot(
            device_id="pci:0000:02:00.0",
            device_kind="gpu",
            vendor="different-vendor",
            model="b9",
            health=ResourceHealth.DEGRADED,
            physical_capacity={"vram.bytes": _measured(48)},
            effective_capacity={"vram.bytes": _derived(40)},
            used_capacity={"vram.bytes": _measured(8)},
            available_capacity={"vram.bytes": _derived(32)},
        ),
    )
    snapshot = service.observe_resource(
        access,
        resource.resource_ref,
        FakeResourceObserver((_observation(0, devices=devices),)),
    )
    assert tuple(item.device_id for item in snapshot.devices) == (
        "pci:0000:01:00.0",
        "pci:0000:02:00.0",
    )
    assert [item.vendor for item in snapshot.devices] == ["vendor-a", "different-vendor"]
    assert snapshot.devices[1].effective_capacity["vram.bytes"].value == 40
    assert snapshot.devices[1].available_capacity["vram.bytes"].value == 32
    device_fit = evaluateResourceFit(
        snapshot,
        ResourceFitRequest(
            required_device_kind="gpu",
            required_device_available={"vram.bytes": 50},
        ),
        at=_time(1),
    )
    assert device_fit.classification is ResourceFit.FIT


def test_t06_configured_physical_effective_used_available_remain_distinct(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    snapshot = service.observe_resource(
        access, resource.resource_ref, FakeResourceObserver((_observation(0),))
    )
    assert resource.configured_capacity["memory.bytes"].value == 128
    assert resource.configured_capacity["memory.bytes"].source_kind is QuantitySource.CONFIGURED
    assert snapshot.physical_capacity["memory.bytes"].value == 64
    assert snapshot.effective_capacity["memory.bytes"].value == 32
    assert snapshot.used_capacity["memory.bytes"].value == 8
    assert snapshot.available_capacity["memory.bytes"].value == 24
    assert all(
        quantity.source_kind is not QuantitySource.CONFIGURED
        for capacity in (
            snapshot.physical_capacity,
            snapshot.effective_capacity,
            snapshot.used_capacity,
            snapshot.available_capacity,
        )
        for quantity in capacity.values()
    )


def test_t07_low_ram_and_cgroup_limits_bound_effective_capacity(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    observation = _observation(
        0,
        physical_memory=64 * 1024,
        effective_memory=8 * 1024,
        used_memory=7 * 1024,
        available_memory=1024,
        runtime_attributes={
            "container.cgroup_version": "2",
            "container.memory_max": str(8 * 1024),
            "container.cpu_max": "200000 100000",
        },
    )
    snapshot = service.observe_resource(
        access, resource.resource_ref, FakeResourceObserver((observation,))
    )
    assert snapshot.physical_capacity["memory.bytes"].value == 64 * 1024
    assert snapshot.effective_capacity["memory.bytes"].value == 8 * 1024
    assert snapshot.available_capacity["memory.bytes"].value == 1024
    assert snapshot.observation.runtime_attributes["container.cgroup_version"] == "2"
    result = evaluateResourceFit(
        snapshot,
        ResourceFitRequest(required_effective={"memory.bytes": 16 * 1024}),
        at=_time(1),
    )
    assert result.classification is ResourceFit.REQUIRES_OTHER_RESOURCE
    assert result.causes == ("effective_insufficient:memory.bytes",)


def test_t08_freshness_and_staleness_are_explicit_and_fail_closed(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    snapshot = service.observe_resource(
        access,
        resource.resource_ref,
        FakeResourceObserver((_observation(0, fresh_for_seconds=2),)),
    )
    assert snapshot.is_fresh(_time(1))
    assert not snapshot.is_fresh(_time(2))
    with pytest.raises(ResourceStaleError):
        service.latest_snapshot(
            access, resource.resource_ref, require_fresh=True, at=_time(3)
        )
    assert service.latest_snapshot(
        access, resource.resource_ref, require_fresh=False
    ) == snapshot
    result = evaluateResourceFit(snapshot, ResourceFitRequest(), at=_time(3))
    assert result.classification is ResourceFit.UNKNOWN
    assert result.causes == ("snapshot_stale",)


def test_t09_changing_vram_creates_chained_history_and_exact_idempotency(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)

    def gpu(available: int) -> ResourceDeviceSnapshot:
        return ResourceDeviceSnapshot(
            device_id="gpu:changing",
            device_kind="gpu",
            vendor="portable-vendor",
            health=ResourceHealth.HEALTHY,
            physical_capacity={"vram.bytes": _measured(80)},
            effective_capacity={"vram.bytes": _derived(80)},
            used_capacity={"vram.bytes": _measured(80 - available)},
            available_capacity={"vram.bytes": _derived(available)},
        )

    first_observation = _observation(0, devices=(gpu(64),))
    second_observation = _observation(1, devices=(gpu(12),))
    observer = FakeResourceObserver((first_observation, second_observation, second_observation))
    first = service.observe_resource(access, resource.resource_ref, observer)
    second = service.observe_resource(access, resource.resource_ref, observer)
    duplicate = service.observe_resource(access, resource.resource_ref, observer)
    assert first.devices[0].available_capacity["vram.bytes"].value == 64
    assert second.devices[0].available_capacity["vram.bytes"].value == 12
    assert first.record_sha256 != second.record_sha256
    assert second.previous_record_sha256 == first.record_sha256
    assert duplicate == second
    assert service.list_snapshots(access, resource.resource_ref) == (first, second)


def test_t10_observer_failure_and_unknown_metrics_are_never_zero_or_healthy(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    snapshot = service.observe_resource(
        access,
        resource.resource_ref,
        FakeResourceObserver((RuntimeError("sensor unavailable"),)),
    )
    assert snapshot.health is ResourceHealth.UNKNOWN
    assert snapshot.failure_causes == ("RuntimeError:sensor unavailable",)
    assert snapshot.physical_capacity == {}
    assert snapshot.available_capacity == {}
    assert not snapshot.is_fresh(snapshot.observed_at)
    result = evaluateResourceFit(
        snapshot,
        ResourceFitRequest(required_available={"memory.bytes": 1}),
        at=snapshot.observed_at,
    )
    assert result.classification is ResourceFit.UNKNOWN
    assert result.causes == ("observer_failure:RuntimeError:sensor unavailable",)


def test_t11_model_tool_cache_artifact_and_workspace_locality_round_trip(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    artifacts = ArtifactService(service.database_path)
    artifact = artifacts.create_artifact(
        access,
        project_ref=resource.project_ref,
        role="resource.locality",
        content_ref=ContentRef.from_bytes(b"local", media_type="text/plain"),
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="resource.observed",
        metadata={},
    )
    artifact_locality = ResourceArtifactLocality(
        artifact.artifact_ref,
        artifact.record_sha256,
    )
    workspace_locality = ResourceWorkspaceLocality(
        resource.project_ref,
        "workspace://current",
    )
    locality = ResourceLocality(
        loaded_model_refs=("model://loaded/a",),
        local_model_refs=("model://local/a",),
        installed_tool_refs=("tool://python/3",),
        warm_cache_refs=("cache://weights/a",),
        local_artifact_refs=(artifact_locality,),
        local_workspace_refs=(workspace_locality,),
    )
    snapshot = service.observe_resource(
        access,
        resource.resource_ref,
        FakeResourceObserver((_observation(0, locality=locality),)),
    )
    assert service.get_snapshot(access, snapshot.snapshot_ref).locality == locality
    assert evaluateResourceFit(
        snapshot,
        ResourceFitRequest(
            required_loaded_model_refs=("model://loaded/a",),
            required_installed_tool_refs=("tool://python/3",),
            required_artifact_refs=(artifact_locality,),
            required_workspace_refs=(workspace_locality,),
        ),
        at=_time(1),
    ).classification is ResourceFit.FIT
    foreign_registration = ProjectStore(service.database_path).create_project(
        namespace="resource-locality-beta",
        display_name="Resource Locality Beta",
    )
    foreign_artifact = artifacts.create_artifact(
        foreign_registration.access,
        project_ref=foreign_registration.project.project_ref,
        role="resource.locality",
        content_ref=ContentRef.from_bytes(b"foreign", media_type="text/plain"),
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="resource.observed",
        metadata={},
    )
    foreign_locality = ResourceLocality(
        local_artifact_refs=(
            ResourceArtifactLocality(
                foreign_artifact.artifact_ref,
                foreign_artifact.record_sha256,
            ),
        )
    )
    with pytest.raises(ResourceScopeError):
        service.record_observation(
            access,
            resource.resource_ref,
            "test.reference",
            _observation(1, locality=foreign_locality),
        )
    connection = sqlite3.connect(service.database_path)
    try:
        connection.execute("DROP TRIGGER artifact_revisions_no_update")
        connection.execute(
            """
            UPDATE artifact_revisions SET record_sha256 = ?
            WHERE project_id = ? AND artifact_id = ? AND revision = ?
            """,
            (
                "0" * 64,
                artifact.project_ref.value,
                artifact.artifact_id,
                artifact.revision,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(ResourceIntegrityError):
        service.get_snapshot(access, snapshot.snapshot_ref)
    with pytest.raises(ResourceIntegrityError):
        service.latest_snapshot(
            access,
            resource.resource_ref,
            require_fresh=False,
        )


def test_t12_unhealthy_then_recovered_preserves_history_and_current_truth(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    observer = FakeResourceObserver(
        (
            _observation(0, health=ResourceHealth.UNHEALTHY),
            _observation(1, health=ResourceHealth.HEALTHY),
        )
    )
    unhealthy = service.observe_resource(access, resource.resource_ref, observer)
    recovered = service.observe_resource(access, resource.resource_ref, observer)
    assert unhealthy.health is ResourceHealth.UNHEALTHY
    assert recovered.health is ResourceHealth.HEALTHY
    assert recovered.previous_record_sha256 == unhealthy.record_sha256
    assert service.list_snapshots(access, resource.resource_ref) == (unhealthy, recovered)
    assert service.get_snapshot(access, unhealthy.snapshot_ref).health is ResourceHealth.UNHEALTHY
    assert service.latest_snapshot(
        access, resource.resource_ref, require_fresh=True, at=_time(2)
    ) == recovered


def test_t13_fit_returns_all_five_exact_classifications_without_weakening(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    snapshot = service.observe_resource(
        access,
        resource.resource_ref,
        FakeResourceObserver((_observation(0, available_memory=4),)),
    )
    evaluated = {
        evaluateResourceFit(
            snapshot,
            ResourceFitRequest(required_available={"memory.bytes": 2}),
            at=_time(1),
        ).classification,
        evaluateResourceFit(
            snapshot,
            ResourceFitRequest(
                required_available={"memory.bytes": 8},
                reduced_available={"memory.bytes": 4},
            ),
            at=_time(1),
        ).classification,
        evaluateResourceFit(
            snapshot,
            ResourceFitRequest(required_effective={"memory.bytes": 48}),
            at=_time(1),
        ).classification,
        evaluateResourceFit(
            snapshot,
            ResourceFitRequest(required_available={"memory.bytes": 8}),
            at=_time(1),
        ).classification,
        evaluateResourceFit(
            snapshot,
            ResourceFitRequest(required_available={"network.bandwidth_bps": 1}),
            at=_time(1),
        ).classification,
    }
    assert evaluated == set(ResourceFit)
    exact_request = ResourceFitRequest(required_available={"memory.bytes": 8})
    assert dict(exact_request.required_available) == {"memory.bytes": 8.0}
    with pytest.raises(ResourceContractError):
        ResourceFitRequest(required_device_features=("matrix.v9",))
    unusable_devices = (
        ResourceDeviceSnapshot(
            device_id="gpu:unknown",
            device_kind="gpu",
            health=ResourceHealth.UNKNOWN,
        ),
        ResourceDeviceSnapshot(
            device_id="gpu:unhealthy",
            device_kind="gpu",
            health=ResourceHealth.UNHEALTHY,
        ),
    )
    unusable = service.record_observation(
        access,
        resource.resource_ref,
        "test.reference",
        _observation(2, devices=unusable_devices),
    )
    assert evaluateResourceFit(
        unusable,
        ResourceFitRequest(required_device_kind="gpu"),
        at=_time(3),
    ).classification is ResourceFit.UNKNOWN
    degraded = service.record_observation(
        access,
        resource.resource_ref,
        "test.reference",
        _observation(3, health=ResourceHealth.DEGRADED),
    )
    assert evaluateResourceFit(
        degraded,
        ResourceFitRequest(),
        at=_time(4),
    ).classification is ResourceFit.TEMPORARILY_UNAVAILABLE


def test_t14_resource_shortage_or_gpu_removal_does_not_mutate_capability(tmp_path: Path) -> None:
    service, access, resource = _inventory(tmp_path)
    registry = CapabilityRegistry(service.database_path)
    capability = registry.register(
        Capability(
            capability_ref=CapabilityRef("compute.matrix", "1.0.0"),
            description="Provider-neutral matrix computation",
        )
    )
    gpu = ResourceDeviceSnapshot(
        device_id="gpu:ephemeral",
        device_kind="gpu",
        vendor="any-vendor",
        health=ResourceHealth.HEALTHY,
    )
    observer = FakeResourceObserver(
        (_observation(0, devices=(gpu,)), _observation(1, devices=()))
    )
    service.observe_resource(access, resource.resource_ref, observer)
    removed = service.observe_resource(access, resource.resource_ref, observer)
    result = evaluateResourceFit(
        removed,
        ResourceFitRequest(required_device_kind="gpu"),
        at=_time(2),
    )
    assert result.classification is ResourceFit.REQUIRES_OTHER_RESOURCE
    after = registry.get(capability.capability_ref)
    assert after == capability
    assert after.contract_sha256 == capability.contract_sha256


def test_t15_predecessor_type_build_and_installed_restart_gates_pass() -> None:
    source_paths = (
        ROOT / "src/biella/resource.py",
        ROOT / "tests/test_p1_07_resource_inventory.py",
        ROOT / "tests/fixtures/p1_07_installed_writer.py",
        ROOT / "tests/fixtures/p1_07_installed_reader.py",
    )
    prohibited_markers = (
        "TO" "DO",
        "FIX" "ME",
        "place" "holder",
        "@unittest." "skip",
        "pytest.mark." "skip",
        "self." "skipTest",
        "Not" "Implemented",
    )
    for path in source_paths:
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        for marker in prohibited_markers:
            assert marker not in source

    typecheck = subprocess.run(
        (sys.executable, "-m", "mypy", "--strict", "src"),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert typecheck.returncode == 0, f"{typecheck.stdout}\n{typecheck.stderr}"
    predecessor = subprocess.run(
        (sys.executable, "-m", "pytest", "-q", "tests/test_p1_06_checkpoint_resume.py"),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert predecessor.returncode == 0, f"{predecessor.stdout}\n{predecessor.stderr}"
    assert "16 passed" in predecessor.stdout
    assert "skipped" not in predecessor.stdout.lower()

    with tempfile.TemporaryDirectory() as temporary_directory:
        qualification_root = Path(temporary_directory)
        wheel_root = qualification_root / "wheel"
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
        wheel_path = wheels[0]
        package_paths = tuple(sorted((ROOT / "src/biella").glob("*.py")))
        with zipfile.ZipFile(wheel_path) as archive:
            wheel_names = {
                name
                for name in archive.namelist()
                if name.startswith("biella/") and name.endswith(".py")
            }
            assert wheel_names == {f"biella/{path.name}" for path in package_paths}
            for path in package_paths:
                assert hashlib.sha256(
                    archive.read(f"biella/{path.name}")
                ).hexdigest() == hashlib.sha256(path.read_bytes()).hexdigest()
        installed = qualification_root / "installed"
        install = subprocess.run(
            (
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(installed),
                str(wheel_path),
            ),
            cwd=qualification_root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert install.returncode == 0, f"{install.stdout}\n{install.stderr}"
        environment = os.environ.copy()
        environment.update(
            {
                "BIELLA_DATABASE": str(qualification_root / "restart.sqlite3"),
                "BIELLA_INSTALLED": str(installed),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(installed),
            }
        )
        writer = subprocess.run(
            (sys.executable, str(ROOT / "tests/fixtures/p1_07_installed_writer.py")),
            cwd=qualification_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert writer.returncode == 0, f"{writer.stdout}\n{writer.stderr}"
        identity = json.loads(writer.stdout)
        environment.update(
            {
                "BIELLA_PROJECT_ID": identity["project_id"],
                "BIELLA_RESOURCE_ID": identity["resource_id"],
                "BIELLA_SNAPSHOT_ID": identity["snapshot_id"],
                "BIELLA_TOKEN": identity["token"],
            }
        )
        reader = subprocess.run(
            (sys.executable, str(ROOT / "tests/fixtures/p1_07_installed_reader.py")),
            cwd=qualification_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert reader.returncode == 0, f"{reader.stdout}\n{reader.stderr}"


def test_resource_snapshot_sql_rows_are_immutable_and_tampering_is_detected(
    tmp_path: Path,
) -> None:
    service, access, resource = _inventory(tmp_path)
    first = service.observe_resource(
        access, resource.resource_ref, FakeResourceObserver((_observation(0),))
    )
    snapshot = service.observe_resource(
        access, resource.resource_ref, FakeResourceObserver((_observation(1),))
    )
    connection = sqlite3.connect(service.database_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE resource_snapshots SET health = 'UNKNOWN' WHERE snapshot_id = ?",
                (snapshot.snapshot_ref.snapshot_id,),
            )
        connection.rollback()
        original_head = connection.execute(
            "SELECT head_sha256 FROM resource_snapshot_heads WHERE snapshot_id = ?",
            (snapshot.snapshot_ref.snapshot_id,),
        ).fetchone()
        assert original_head is not None
        connection.execute(
            "UPDATE resource_snapshot_heads SET head_sha256 = ? WHERE snapshot_id = ?",
            ("0" * 64, snapshot.snapshot_ref.snapshot_id),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(ResourceIntegrityError):
        service.latest_snapshot(
            access,
            resource.resource_ref,
            require_fresh=False,
        )
    connection = sqlite3.connect(service.database_path)
    try:
        connection.execute(
            "UPDATE resource_snapshot_heads SET head_sha256 = ? WHERE snapshot_id = ?",
            (original_head[0], snapshot.snapshot_ref.snapshot_id),
        )
        connection.execute("DROP TRIGGER resource_snapshots_no_delete")
        connection.execute(
            "DELETE FROM resource_snapshots WHERE snapshot_id = ?",
            (first.snapshot_ref.snapshot_id,),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(ResourceIntegrityError):
        service.get_snapshot(access, snapshot.snapshot_ref)
    with pytest.raises(ResourceIntegrityError):
        service.latest_snapshot(
            access,
            resource.resource_ref,
            require_fresh=False,
        )
