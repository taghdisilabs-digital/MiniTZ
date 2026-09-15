#!/usr/bin/env bash
set -Eeuo pipefail

# Docker-free builder for the Ubuntu 26.04 sandbox.  It uses debootstrap to
# create the same isolated rootfs contract as ImageRootfs.Dockerfile, then
# delegates disk layout and source identity to image-layout.sh.
SANDBOX=${MINITZ_OS_SANDBOX_ROOT:-/root/attached-storage/minitz-os-sandbox}
REPO="$SANDBOX/workspace/repo"
STATE="$SANDBOX/state/image-build"
OUTPUT=${1:-$SANDBOX/output/images}
MIRROR=${MINITZ_UBUNTU_MIRROR:-http://archive.ubuntu.com/ubuntu}
SUITE=${MINITZ_UBUNTU_SUITE:-resolute}

command -v debootstrap >/dev/null || { echo 'debootstrap is required in the sandbox' >&2; exit 127; }
for tool in mkfs.ext4 mkfs.vfat mcopy mmd grub-mkstandalone sgdisk; do
    command -v "$tool" >/dev/null || { echo "$tool is required in the sandbox" >&2; exit 127; }
done

mkdir -p "$STATE" "$OUTPUT"
rm -rf "$STATE/context" "$STATE/rootfs"
mkdir -p "$STATE/context/source" "$STATE/rootfs"

PYTHONPATH="$REPO/src" python3 - "$REPO" "$STATE/context" <<'PY'
import shutil
import sys
from pathlib import Path
from minitz_os.source import canonical, source_manifest

root = Path(sys.argv[1]).resolve()
context = Path(sys.argv[2]).resolve()
manifest = source_manifest(root)
for relative in manifest["files"]:
    source = root / relative
    target = context / "source" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
(context / "source.json").write_bytes(canonical(manifest) + b"\n")
print(manifest["source_sha256"])
PY

SOURCE_SHA=$(python3 -c 'import json;print(json.load(open("'$STATE'/context/source.json"))["source_sha256"])')
DEBOOTSTRAP_LOG="$STATE/debootstrap.log"
DEBOOTSTRAP_INCLUDE='ca-certificates,python3,systemd-sysv,linux-image-generic,initramfs-tools,xorg,xfce4,lightdm,network-manager,network-manager-gnome,network-manager-openvpn,network-manager-openvpn-gnome,openvpn,wireguard-tools'
debootstrap --variant=minbase --include="$DEBOOTSTRAP_INCLUDE" "$SUITE" "$STATE/rootfs" "$MIRROR" >"$DEBOOTSTRAP_LOG" 2>&1

mkdir -p "$STATE/rootfs/opt/minitz/source" "$STATE/rootfs/etc/minitz" "$STATE/rootfs/usr/bin"
cp -a "$STATE/context/source/." "$STATE/rootfs/opt/minitz/source/"
cp "$STATE/context/source.json" "$STATE/rootfs/etc/minitz/source.json"
cp "$REPO/ops/workstation/minitz-os-sandbox/preinstall.json" "$STATE/rootfs/etc/minitz/preinstall.json"
cp "$REPO/ops/workstation/minitz-os-sandbox/accessibility-profile.json" "$STATE/rootfs/etc/minitz/accessibility-profile.json"
chroot "$STATE/rootfs" useradd -m -s /bin/bash minitz
chroot "$STATE/rootfs" passwd -l minitz
mkdir -p "$STATE/rootfs/etc/lightdm/lightdm.conf.d"
printf '[Seat:*]\nautologin-user=minitz\nautologin-user-timeout=0\nuser-session=xfce\n' >"$STATE/rootfs/etc/lightdm/lightdm.conf.d/50-minitz.conf"
chroot "$STATE/rootfs" systemctl set-default graphical.target
chroot "$STATE/rootfs" systemctl enable NetworkManager.service lightdm.service
mkdir -p "$STATE/rootfs/usr/local/libexec"
cp "$STATE/rootfs/opt/minitz/source/ops/workstation/minitz-os-sandbox/minitz-boot-proof.sh" "$STATE/rootfs/usr/local/libexec/minitz-boot-proof"
chmod 0755 "$STATE/rootfs/usr/local/libexec/minitz-boot-proof"
cp "$REPO/ops/workstation/minitz-os-sandbox/minitz-boot-proof.service" "$STATE/rootfs/etc/systemd/system/minitz-boot-proof.service"
mkdir -p "$STATE/rootfs/etc/systemd/system/multi-user.target.wants"
ln -sf ../minitz-boot-proof.service "$STATE/rootfs/etc/systemd/system/multi-user.target.wants/minitz-boot-proof.service"
cat >"$STATE/rootfs/usr/bin/minitz" <<'SH'
#!/bin/sh
export MINITZ_SOURCE_ROOT=/opt/minitz/source
export MINITZ_SOURCE_MANIFEST=/etc/minitz/source.json
export PYTHONPATH=/opt/minitz/source/src${PYTHONPATH:+:$PYTHONPATH}
exec python3 -m minitz_os "$@"
SH
chmod 0755 "$STATE/rootfs/usr/bin/minitz"
printf 'LABEL=MINITZROOT / ext4 defaults 0 1\n' >"$STATE/rootfs/etc/fstab"
printf 'minitz-os\n' >"$STATE/rootfs/etc/hostname"
truncate -s 0 "$STATE/rootfs/etc/machine-id"

SOURCE_SHA="$SOURCE_SHA" "$REPO/ops/workstation/minitz-os-sandbox/image-layout.sh" "$STATE"
IMAGE="$STATE/MiniTZ-OS-${SOURCE_SHA:0:16}.raw"
printf '%s\n' local >"$STATE/rootfs-image-tag"
OUTPUT_IMAGE="$OUTPUT/$(basename "$IMAGE")"
cp --reflink=auto --sparse=always "$IMAGE" "$OUTPUT_IMAGE"
PYTHONPATH="$REPO/src" python3 - "$REPO" "$SANDBOX" "$OUTPUT_IMAGE" "$STATE/build.json" <<'PYART'
import sys
from pathlib import Path
from minitz_os.boot_artifact import stage_boot_artifact_candidate
stage_boot_artifact_candidate(*(Path(value) for value in sys.argv[1:]))
PYART
if [ -n "${MINITZ_UPDATE_SIGNING_KEY_FILE:-}" ]; then
    "$REPO/ops/workstation/minitz-os-sandbox/sign-image.sh" "$OUTPUT_IMAGE"
fi
printf '%s\n' "$OUTPUT_IMAGE"
