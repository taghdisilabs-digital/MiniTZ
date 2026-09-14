from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

def test_release_contract_requires_real_bootable_image_field():
    from minitz_os.source import source_manifest
    m=source_manifest(ROOT)
    assert m["product"]=="MiniTZ OS"
    assert m["base_os"]=="Ubuntu 26.04"
    assert m["bootable_disk_image"] is True
    assert m["artifact_kind"]=="BOOTABLE_DISK_IMAGE"

def test_boot_image_builder_is_sandbox_scoped_and_non_host_mutating():
    script=(ROOT/"ops/workstation/minitz-os-sandbox/build-image.sh").read_text()
    assert "/root/attached-storage/minitz-os-sandbox" in script
    assert "mount /dev" not in script
    assert "systemctl" not in script
    assert "apt-get" not in script
    assert "losetup" not in script

def test_boot_image_validation_is_structural_and_never_boots_image():
    script=(ROOT/"ops/workstation/minitz-os-sandbox/validate-image.sh").read_text()
    assert "qemu-system-x86_64" not in script
    assert "BOOTX64.EFI" in script
    assert "sgdisk" in script
    assert "debugfs" in script
    assert "bootable_disk_image" in script
