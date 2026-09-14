from __future__ import annotations

import hashlib

import pytest

from minitz_os.capabilities import (
    ActionRequest,
    Availability,
    CapabilitySurface,
    CapabilityUnavailableError,
    ResourceContract,
)


REQUIRED_NAMESPACES = {
    "software",
    "web",
    "game",
    "3d",
    "character",
    "animation",
    "render",
    "image",
    "audio",
    "video",
    "filesystem",
    "process",
    "network",
    "model",
    "storage",
    "api",
}


def test_complete_surface_has_action_resource_and_evidence_contracts() -> None:
    surface = CapabilitySurface()
    descriptors = surface.descriptors()

    assert len(descriptors) >= len(REQUIRED_NAMESPACES)
    assert {item.capability.namespace for item in descriptors} >= REQUIRED_NAMESPACES
    assert len({item.capability_ref.value for item in descriptors}) == len(descriptors)
    assert len({item.action.action_ref for item in descriptors}) == len(descriptors)
    assert all(item.action.capability_ref == item.capability_ref for item in descriptors)
    assert all(item.action.implementation_refs for item in descriptors)
    assert all(item.action.evidence_refs for item in descriptors)
    assert all(item.action.resource_profile_ref.startswith("resource-profile://") for item in descriptors)


def test_unobserved_surface_is_truthfully_needs_setup() -> None:
    surface = CapabilitySurface()

    statuses = surface.statuses()
    assert statuses
    assert {item.availability for item in statuses} == {Availability.NEEDS_SETUP}
    assert all(not item.resource_refs for item in statuses)
    assert all("Ready" not in item.reason for item in statuses)
    assert surface.snapshot()["status_counts"][Availability.NEEDS_SETUP.value] == len(statuses)


def test_action_requires_resource_executor_and_evidence_readback() -> None:
    surface = CapabilitySurface()
    descriptor = surface.get("filesystem.read@1.0.0")
    resource = ResourceContract(
        resource_ref="resource://minitz/test/filesystem",
        resource_kind="filesystem",
        availability=Availability.READY,
        evidence_refs=("evidence://minitz/resource/filesystem-test",),
        evidence_sha256=hashlib.sha256(b"resource-observation").hexdigest(),
    )
    surface.register_resource(resource)

    with pytest.raises(CapabilityUnavailableError):
        surface.execute(ActionRequest(
            capability_ref=descriptor.capability_ref.value,
            action_ref=descriptor.action.action_ref,
            inputs={"path": "workspace/input"},
            resource_ref=resource.resource_ref,
        ))

    implementation_ref = descriptor.action.implementation_refs[0]
    surface.register_executor(
        descriptor.action.action_ref,
        lambda inputs: {"observed_path": inputs["path"], "read": True, "metadata": {"segments": ["workspace", "input"]}},
        implementation_ref=implementation_ref,
    )
    assert surface.status(descriptor.capability_ref.value).availability is Availability.READY
    result = surface.execute(ActionRequest(
        capability_ref=descriptor.capability_ref.value,
        action_ref=descriptor.action.action_ref,
        inputs={"path": "workspace/input"},
        resource_ref=resource.resource_ref,
    ))

    assert result.readback["read"] is True
    assert result.readback["metadata"] == {"segments": ["workspace", "input"]}
    assert result.evidence_ref.startswith("evidence://minitz/action/")
    assert len(result.evidence_sha256) == 64
    assert result.evidence_record.record_sha256 == result.evidence_sha256
    assert result.evidence_record.payload["resource_evidence_refs"] == tuple(resource.evidence_refs)


def test_raw_credentials_are_rejected_before_executor() -> None:
    surface = CapabilitySurface()
    descriptor = surface.get("api.request@1.0.0")
    resource = ResourceContract(
        resource_ref="resource://minitz/test/network",
        resource_kind="network",
        availability=Availability.READY,
        evidence_refs=("evidence://minitz/resource/network-test",),
        evidence_sha256=hashlib.sha256(b"network-observation").hexdigest(),
    )
    surface.register_resource(resource)
    surface.register_executor(
        descriptor.action.action_ref,
        lambda inputs: {"request": inputs},
        implementation_ref=descriptor.action.implementation_refs[0],
    )

    with pytest.raises(ValueError):
        surface.execute(ActionRequest(
            capability_ref=descriptor.capability_ref.value,
            action_ref=descriptor.action.action_ref,
            inputs={"api_key": "raw-secret-value"},
            resource_ref=resource.resource_ref,
        ))
