"""Inspect actual disk filesystem defaults without mounting or booting it."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from minitz_os.source import source_manifest


def debug(command):
    completed = subprocess.run(["debugfs", "-R", command, "/image/root.img"],
                               capture_output=True, check=True)
    assert b"not found" not in completed.stderr, command
    return completed.stdout


def read(path):
    return debug("cat " + path)


repo = Path("/workspace/repo")
identity = source_manifest(repo)
result = {"state": "PASS", "source_sha256": identity["source_sha256"],
          "image_boot_executed": False,
          "scope": "Actual validated image bytes: installed packages, executable modes, desktop/network defaults, credential defaults and profiles. No running desktop or VPN connection is claimed."}
status = read("/var/lib/dpkg/status").decode()
packages = {}
for paragraph in status.split("\n\n"):
    fields = dict(line.split(": ", 1) for line in paragraph.splitlines()
                  if ": " in line and not line.startswith(" "))
    if fields.get("Status") == "install ok installed":
        packages[fields["Package"]] = fields["Version"]
required = ["systemd-sysv", "linux-image-generic", "python3", "xorg", "xfce4", "lightdm",
            "network-manager", "network-manager-gnome", "network-manager-openvpn",
            "network-manager-openvpn-gnome", "openvpn", "wireguard-tools"]
assert all(package in packages for package in required)
result["installed_packages"] = {package: packages[package] for package in required}
result["executable_modes"] = {}
for path in ["/usr/bin/minitz", "/usr/sbin/NetworkManager", "/usr/sbin/lightdm",
             "/usr/bin/startxfce4", "/usr/bin/nm-connection-editor", "/usr/sbin/openvpn",
             "/usr/bin/wg", "/usr/lib/xorg/Xorg", "/usr/local/libexec/minitz-boot-proof"]:
    metadata = debug("stat " + path).decode()
    match = re.search(r"Type: regular\s+Mode:\s+(0[0-7]+)", metadata)
    assert match and int(match[1], 8) & 0o111, path
    result["executable_modes"][path] = match[1]
links = {
    "/etc/systemd/system/default.target": "/usr/lib/systemd/system/graphical.target",
    "/etc/systemd/system/display-manager.service": "/lib/systemd/system/lightdm.service",
    "/etc/systemd/system/multi-user.target.wants/NetworkManager.service": "/usr/lib/systemd/system/NetworkManager.service",
    "/etc/systemd/system/multi-user.target.wants/minitz-boot-proof.service": "../minitz-boot-proof.service",
}
for path, target in links.items():
    assert 'Fast link dest: "' + target + '"' in debug("stat " + path).decode(), path
result["service_enablement_links"] = links
profiles = {}
for filename in ["preinstall.json", "accessibility-profile.json"]:
    data = read("/etc/minitz/" + filename)
    assert data == (repo / "ops/workstation/minitz-os-sandbox" / filename).read_bytes()
    profiles[filename] = {"sha256": hashlib.sha256(data).hexdigest(), "matches_source": True}
result["profiles"] = profiles
lightdm = read("/etc/lightdm/lightdm.conf.d/50-minitz.conf").decode()
assert "autologin-user=minitz\n" in lightdm and "user-session=xfce\n" in lightdm
result["desktop_session_default"] = "minitz / XFCE local autologin"
shadow = [line.split(":") for line in read("/etc/shadow").decode().splitlines()]
assert any(fields[0] == "minitz" for fields in shadow)
assert all(fields[1] and set(fields[1]) <= {"!", "*"} for fields in shadow)
result["credential_defaults"] = {"all_account_passwords_locked_without_hashes": True,
                                 "password_values_recorded": False}
assert read("/etc/machine-id") == b""
result["machine_identity_uninitialized"] = True
print(json.dumps(result, indent=2))
