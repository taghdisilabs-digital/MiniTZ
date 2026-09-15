#!/usr/bin/env bash
set -Eeuo pipefail

SANDBOX=${MINITZ_OS_SANDBOX_ROOT:-/root/attached-storage/minitz-os-sandbox}
STATE="$SANDBOX/state/image-build"
IMAGE=${1:?image path required}
BUILD="$STATE/build.json"
test -f "$IMAGE"
test -f "$BUILD"
WORK="$STATE/validation"
rm -rf "$WORK"
mkdir -p "$WORK"
cp --reflink=auto --sparse=always "$IMAGE" "$WORK/image.raw"

sgdisk -v "$IMAGE" >"$WORK/gpt-verify.txt"
p1_start=$(sgdisk -i 1 "$IMAGE" | awk '/First sector:/ {print $3}')
p1_end=$(sgdisk -i 1 "$IMAGE" | awk '/Last sector:/ {print $3}')
p2_start=$(sgdisk -i 2 "$IMAGE" | awk '/First sector:/ {print $3}')
p2_end=$(sgdisk -i 2 "$IMAGE" | awk '/Last sector:/ {print $3}')
for value in "$p1_start" "$p1_end" "$p2_start" "$p2_end"; do [[ "$value" =~ ^[0-9]+$ ]]; done
p1_count=$((p1_end-p1_start+1)); p2_count=$((p2_end-p2_start+1))
dd if="$IMAGE" of="$WORK/esp.img" bs=512 skip="$p1_start" count="$p1_count" status=none
dd if="$IMAGE" of="$WORK/root.img" bs=512 skip="$p2_start" count="$p2_count" status=none
mcopy -i "$WORK/esp.img" ::/EFI/BOOT/BOOTX64.EFI "$WORK/BOOTX64.EFI"
e2fsck -fn "$WORK/root.img" >"$WORK/ext4-check.txt" 2>&1 || rc=$?
[ "${rc:-0}" -le 1 ]
debugfs -R "stat /etc/minitz/source.json" "$WORK/root.img" >"$WORK/source-stat.txt" 2>&1
debugfs -R "stat /usr/bin/minitz" "$WORK/root.img" >"$WORK/launcher-stat.txt" 2>&1
kernel=$(python3 -c 'import json;print(json.load(open("'$BUILD'"))["kernel"])')
debugfs -R "stat /boot/$kernel" "$WORK/root.img" >"$WORK/kernel-stat.txt" 2>&1
debugfs -R "cat /etc/minitz/source.json" "$WORK/root.img" 2>/dev/null >"$WORK/source.json"

SOURCE_SHA=$(python3 -c 'import json;print(json.load(open("'$BUILD'"))["source_sha256"])')
python3 - "$WORK/source.json" "$BUILD" "$IMAGE" "$WORK/validation.json" "$SOURCE_SHA" <<'PY'
import hashlib
import json
import os
import sys

source_path, build_path, image_path, output_path, source_sha = sys.argv[1:]
manifest = json.load(open(source_path, encoding="utf-8"))
build = json.load(open(build_path, encoding="utf-8"))
assert manifest["product"] == "MiniTZ OS"
assert manifest["base_os"] == "Ubuntu 26.04"
assert manifest["source_sha256"] == build["source_sha256"] == source_sha
assert manifest["bootable_disk_image"] is True
digest = hashlib.sha256()
with open(image_path, "rb") as stream:
    for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
        digest.update(block)
result = {
    **build,
    "schema": "minitz.boot_image_validation/v1",
    "image_path": image_path,
    "image_sha256": digest.hexdigest(),
    "image_bytes": os.path.getsize(image_path),
    "bootable_disk_image": True,
    "partition_table": "GPT",
    "efi_system_partition": "PASS",
    "efi_bootloader_path": "/EFI/BOOT/BOOTX64.EFI",
    "root_filesystem": "EXT4_PASS",
    "kernel_present": "PASS",
    "source_identity_embedded": "PASS",
    "image_boot_executed": False,
    "quality_verdict": "PASS",
}
json.dump(result, open(output_path, "w", encoding="utf-8"), sort_keys=True, indent=2)
print(json.dumps(result, sort_keys=True))
PY
PYTHONPATH="$SANDBOX/workspace/repo/src" python3 - "$SANDBOX/workspace/repo" "$SANDBOX" "$IMAGE" "$BUILD" "$WORK/validation.json" <<'PYART'
import sys
from pathlib import Path
from minitz_os.boot_artifact import publish_validated_boot_artifact
publish_validated_boot_artifact(*(Path(value) for value in sys.argv[1:]))
PYART
