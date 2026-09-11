from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "ops/workstation/minitz-browser-cloud.py"
MANIFEST = ROOT / "ops/workstation/windows-browser-cloud-targets.json"
REGISTRY = ROOT / "ops/workstation/provider-registry.json"
INSTALLER = ROOT / "ops/workstation/install-biella-workstation.sh"

spec = importlib.util.spec_from_file_location("minitz_browser_cloud", ADAPTER)
assert spec and spec.loader
browser = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = browser
spec.loader.exec_module(browser)


def test_manifest_binds_exact_two_ready_cpanel_targets_without_secrets():
    manifest = browser.load_manifest(MANIFEST)
    assert manifest["authority"] == "NONE"
    assert set(manifest["targets"]) == {"crazcodez", "taghdisilabs"}
    assert manifest["targets"]["crazcodez"]["primary_domain"] == "crazcodez.com"
    assert manifest["targets"]["taghdisilabs"]["primary_domain"] == "taghdisilabs.digital"
    encoded = json.dumps(manifest).lower()
    for forbidden in ("cpsess", "cookie", "password", "api_token", "private_key"):
        assert forbidden not in encoded

def test_provider_registry_routes_browser_and_cpanel_to_non_authoritative_resource():
    registry = json.loads(REGISTRY.read_text())
    provider = registry["providers"]["windows-browser-cloud"]
    assert provider["authority"] == "RESOURCE_IMPLEMENTATION"
    assert provider["scope"] == "AUTHENTICATED_BROWSER_RESOURCE_ONLY"
    assert provider["target_manifest"].endswith("windows-browser-cloud-targets.json")
    assert registry["routes"]["browser.actions"] == ["windows-browser-cloud"]
    assert registry["routes"]["hosting.cpanel"] == ["windows-browser-cloud"]


def test_unknown_target_fails_before_transport():
    with pytest.raises(browser.BrowserCloudError, match="unknown browser target"):
        browser.bridge_request("activate", target="not-configured", timeout=2)


def test_workstation_installer_persists_adapter_and_cli_link():
    text = INSTALLER.read_text()
    assert '"$SOURCE_DIR/minitz-browser-cloud.py"' in text
    assert '"$SOURCE_DIR/windows-browser-cloud-targets.json"' in text
    assert 'BROWSER_CLOUD_LINK="/usr/local/bin/minitz-browser-cloud"' in text
    assert 'ensure_link "$BROWSER_CLOUD_LINK" "$INSTALL_DIR/minitz-browser-cloud.py"' in text
