"""Installer tooling only: fixture payloads never count as game/runtime proof."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer_resource", ROOT / "ops/workstation/minitz-resource.py")
resource = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resource)


def test_installer_routes_are_real_local_tools_not_cross_compilers():
    registry = resource.load_registry(ROOT / "ops/workstation/provider-registry.json")
    for capability, provider, command in (
        ("package.installer.debian", "dpkg-deb", "dpkg-deb"),
        ("package.installer.windows", "nsis", "makensis"),
    ):
        assert resource.route_capability(registry, capability, env={}, command_exists=lambda c: c == command) == [provider]
        assert registry["providers"][provider]["scope"] == "INSTALLER_ASSEMBLY_ONLY"
        assert not registry["providers"][provider]["required_env"]
    assert "nsis" not in resource.route_capability(registry, "unreal.build.win64", env={}, command_exists=lambda c: True)


def test_guide_and_map_bind_installer_instructions_without_os_changes():
    guide = (ROOT / "projects/minitz-games/docs/task-guides/D08-01.md").read_text()
    assert "INSTALLER_ASSEMBLY_ONLY" in guide
    assert "ops/workstation/INSTALLERS.md" in guide
    mapping = json.loads((ROOT / "docs/task-program/D_NEXT_100_TASKS.json").read_text())
    row = next(x for x in mapping["tasks"] if x["task_id"] == "D08-01")
    assert {"package.installer.debian", "package.installer.windows"} <= set(row["resource_capabilities"])
    ref = next(x for x in row["source_refs"] if x["path"] == "ops/workstation/INSTALLERS.md")
    assert ref["sha256"] == hashlib.sha256((ROOT / ref["path"]).read_bytes()).hexdigest()
    assert "Primary target platform: Windows PC x64 first." in guide


def test_installer_installation_does_not_control_production_or_replace_os():
    text = (ROOT / "ops/workstation/install-package-tools.sh").read_text()
    assert "--no-install-recommends" in text
    assert "nsis" in text and "dpkg" in text
    for forbidden in ("systemctl", "autoremove", "dist-upgrade", "qemu", "wine", "steam", "gnome", "kde"):
        assert forbidden not in text


def test_native_debian_package_build_extract_exact_bytes(tmp_path):
    if not shutil.which("dpkg-deb"):
        pytest.skip("dpkg-deb not installed on this test host")
    tree = tmp_path / "deb-root"
    (tree / "DEBIAN").mkdir(parents=True)
    (tree / "DEBIAN/control").write_text("Package: installer-tool-probe\nVersion: 1.0\nArchitecture: all\nMaintainer: MiniTZ installer test\nDescription: Tool fixture only, not a game release\n")
    data = b"INSTALLER_TOOL_FIXTURE_NOT_GAME_RELEASE\n"
    payload = tree / "usr/share/installer-tool-probe/payload.txt"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(data)
    out = tmp_path / "probe.deb"
    subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(tree), str(out)], check=True, capture_output=True)
    extracted = tmp_path / "deb-extracted"
    subprocess.run(["dpkg-deb", "--extract", str(out), str(extracted)], check=True, capture_output=True)
    assert (extracted / "usr/share/installer-tool-probe/payload.txt").read_bytes() == data


def test_native_windows_installer_build_extract_exact_bytes(tmp_path):
    if not shutil.which("makensis") or not shutil.which("7z"):
        pytest.skip("NSIS/7z not installed on this test host")
    payload = tmp_path / "payload.txt"
    payload.write_bytes(b"INSTALLER_TOOL_FIXTURE_NOT_GAME_RELEASE\n")
    script = tmp_path / "probe.nsi"
    output = tmp_path / "probe.exe"
    script.write_text('Unicode True\nName "Installer tool probe"\nOutFile "' + str(output) + '"\nRequestExecutionLevel user\nInstallDir "$LOCALAPPDATA\\InstallerToolProbe"\nSection\nSetOutPath "$INSTDIR"\nFile "' + str(payload) + '"\nSectionEnd\n')
    subprocess.run(["makensis", "-V2", str(script)], check=True, capture_output=True)
    blob = output.read_bytes()
    assert blob[:2] == b"MZ"
    pe = int.from_bytes(blob[60:64], "little")
    assert blob[pe:pe + 4] == b"PE\0\0"
    extracted = tmp_path / "nsis-extracted"
    subprocess.run(["7z", "x", "-y", "-o" + str(extracted), str(output)], check=True, capture_output=True)
    assert (extracted / "payload.txt").read_bytes() == payload.read_bytes()
