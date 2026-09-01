from __future__ import annotations

from dataclasses import replace

import pytest

from biella.artifact import ArtifactRef, ContentRef
from biella.delivery_pack import (
    DeliveryArtifactContentRef,
    DeliveryContractError,
    PackageEntry,
    PackageManifest,
    PublishDestination,
    PublishReceipt,
    PublishRequest,
    delivery_production_pack,
)
from biella.graph import GraphRef, NodeRef
from biella.production_pack import ProductionPackRef
from biella.project import ProjectRef
from biella.run import RunRef
from biella.task import TaskRef


CAPABILITIES = {
    "package.assemble", "package.manifest", "package.archive", "package.compress",
    "package.installable", "package.sign", "package.verify", "publish.upload",
    "publish.deploy", "publish.release", "publish.distribute", "publish.verify",
    "delivery.copy", "delivery.sync", "delivery.verify",
}
ATTEMPT = "natt_" + "d" * 32


def _identity(project_ref: ProjectRef) -> tuple[TaskRef, RunRef, GraphRef, NodeRef]:
    task = TaskRef(project_ref, "tsk_" + "a" * 32, 1)
    run = RunRef(project_ref, "run_" + "b" * 32)
    graph = GraphRef(project_ref, "gph_" + "c" * 32, 1)
    return task, run, graph, NodeRef(graph, "nod_" + "d" * 32)


def _source(project_ref: ProjectRef, digest: str) -> DeliveryArtifactContentRef:
    return DeliveryArtifactContentRef(ArtifactRef(project_ref, "art_" + "e" * 32, 1), ContentRef("sha256", digest, 3, "application/octet-stream"))


def _manifest(project_ref: ProjectRef) -> PackageManifest:
    task, run, graph, _ = _identity(project_ref)
    source = _source(project_ref, "a" * 64)
    entry = PackageEntry("bin/app", "a" * 64, 3, "application/octet-stream", "0755", "forbid")
    return PackageManifest.create(project_ref, "pkg-main", task, run, graph, "wheel", "target://python/wheel/v1", (source,), (entry,), "source://git/main/v1", "build://biella/v1", {"python": "3.14"}, "b" * 64, None, "2026-09-01T00:00:00+00:00")


def test_delivery_pack_registers_exact_capabilities() -> None:
    pack = delivery_production_pack()
    assert pack.pack_ref == ProductionPackRef("delivery", "1.0.0")
    assert {item.capability_id for item in pack.capability_definitions} == CAPABILITIES
    assert {"delivery.package", "delivery.manifest", "delivery.archive", "delivery.signature", "delivery.receipt", "delivery.validation-evidence"} <= set(pack.artifact_roles)


def test_package_manifest_isolated_entries_and_canonical_identity_fail_closed() -> None:
    project_ref = ProjectRef.new()
    manifest = _manifest(project_ref)
    assert manifest.entries[0].path == "bin/app"
    with pytest.raises(DeliveryContractError, match="path"):
        PackageEntry("../escape", "a" * 64, 3, "application/octet-stream", "0644", "forbid")
    with pytest.raises(DeliveryContractError, match="duplicate"):
        PackageManifest.create(project_ref, "pkg-main", manifest.task_ref, manifest.run_ref, manifest.graph_ref, "wheel", "target://python/wheel/v1", manifest.sources, (manifest.entries[0], manifest.entries[0]), "source://git/main/v1", "build://biella/v1", {}, "b" * 64, None, "2026-09-01T00:00:00+00:00")
    with pytest.raises(DeliveryContractError, match="manifest_digest"):
        replace(manifest, package_id="forged")


def test_publish_scope_request_and_receipt_states_are_fail_closed() -> None:
    project_ref = ProjectRef.new()
    manifest = _manifest(project_ref)
    _, _, _, node = _identity(project_ref)
    destination = PublishDestination(project_ref, False, "adapter://delivery/http/v1", "registry", "endpoint://registry/example/v1", "secret://publish/token/v1", ("target://python/wheel/v1",), "policy://data/internal/v1")
    request = PublishRequest.create(manifest, destination, "target://python/wheel/v1", "release://biella/v1", "upload", False, "verification://sha256/v1", manifest.task_ref, manifest.run_ref, node, "idem_delivery_001")
    receipt = PublishReceipt.create(request, "VERIFIED", "remote://registry/pkg-main/1", "1.0.0", "c" * 64, "evidence://verification/pkg-main/v1", "2026-09-01T00:00:01+00:00", None)
    assert receipt.state == "VERIFIED"
    with pytest.raises(DeliveryContractError, match="verification"):
        PublishReceipt.create(request, "VERIFIED", "remote://registry/pkg-main/1", "1.0.0", "c" * 64, None, "2026-09-01T00:00:01+00:00", None)
    with pytest.raises(DeliveryContractError, match="Project"):
        PublishRequest.create(manifest, PublishDestination(ProjectRef.new(), False, "adapter://delivery/http/v1", "registry", "endpoint://registry/example/v1", "secret://publish/token/v1", ("target://python/wheel/v1",), "policy://data/internal/v1"), "target://python/wheel/v1", "release://biella/v1", "upload", False, "verification://sha256/v1", manifest.task_ref, manifest.run_ref, node, "idem_delivery_002")
