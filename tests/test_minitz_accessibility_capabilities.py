from __future__ import annotations

import json
from pathlib import Path

from minitz_os.capabilities import (
    ActionRequest,
    Availability,
    CapabilitySurface,
    configure_accessibility_capabilities,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "ops/workstation/minitz-os-sandbox/accessibility-profile.json"
CAPABILITIES = {
    "runtime.offline@1.0.0": "offline_core",
    "network.data_saver@1.0.0": "data_saver",
    "ui.text_only@1.0.0": "text_control",
    "runtime.low_resource@1.0.0": "low_resource",
}


def test_accessibility_profile_keeps_core_local_and_provider_independent() -> None:
    profile = json.loads(PROFILE.read_text())
    assert profile["schema"] == "minitz.accessibility_profile/v1"
    assert profile["offline_core"]["required_remote_providers"] == 0
    assert profile["data_saver"]["local_first"] is True
    assert profile["data_saver"]["reuse_cached_results"] is True
    assert profile["data_saver"]["duplicate_equivalent_fanout"] is False
    assert profile["data_saver"]["remote_only_when_required"] is True
    assert profile["text_control"]["desktop_required"] is False
    assert profile["text_control"]["browser_required"] is False
    assert profile["low_resource"]["gpu_required_for_core"] is False
    assert profile["low_resource"]["frontier_remote_required_for_core"] is False
    assert profile["low_resource"]["preserve_full_quality_when_resources_available"] is True


def test_accessibility_capabilities_are_executable_from_installed_profile() -> None:
    surface = CapabilitySurface()
    resource = configure_accessibility_capabilities(surface, ROOT)
    for capability_ref, section in CAPABILITIES.items():
        descriptor = surface.get(capability_ref)
        assert surface.status(capability_ref).availability is Availability.READY
        result = surface.execute(ActionRequest(
            capability_ref=capability_ref,
            action_ref=descriptor.action.action_ref,
            inputs={},
            resource_ref=resource.resource_ref,
        ))
        assert result.readback["profile_section"] == section
        assert result.readback["enabled"] is True
        assert len(result.evidence_sha256) == 64


def test_image_builders_install_accessibility_profile() -> None:
    dockerfile = (PROFILE.parent / "ImageRootfs.Dockerfile").read_text()
    local_builder = (PROFILE.parent / "build-image-local.sh").read_text()
    target = "/etc/minitz/accessibility-profile.json"
    assert target in dockerfile
    assert target in local_builder


def test_capabilities_cli_binds_accessibility_profile() -> None:
    cli = (ROOT / "src/minitz_os/__main__.py").read_text()
    assert "configure_accessibility_capabilities(surface, root)" in cli
    assert 'result["capability_surface"] = surface.snapshot()' in cli


def test_accessibility_profile_is_part_of_canonical_source_identity() -> None:
    from minitz_os.source import source_manifest

    manifest = source_manifest(ROOT)
    assert "ops/workstation/minitz-os-sandbox/accessibility-profile.json" in manifest["files"]
