#!/usr/bin/env bash
set -Eeuo pipefail
SANDBOX=${MINITZ_OS_SANDBOX_ROOT:-/root/attached-storage/minitz-os-sandbox}
REPO="$SANDBOX/workspace/repo"
STATE="$SANDBOX/state/image-build"
IMAGE=${1:?image path required}
test -f "$IMAGE"
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    exec "$SANDBOX/workspace/repo/ops/workstation/minitz-os-sandbox/validate-image-local.sh" "$IMAGE"
fi
TAG=$(cat "$STATE/rootfs-image-tag")
WORK="$STATE/validation"
rm -rf "$WORK"
mkdir -p "$WORK"
cp --reflink=auto --sparse=always "$IMAGE" "$WORK/image.raw"
SOURCE_SHA=$(python3 -c 'import json;print(json.load(open("'$STATE'/build.json"))["source_sha256"])')
docker run --rm -e SOURCE_SHA="$SOURCE_SHA" -v "$WORK:/build" -v "$STATE/build.json:/build.json:ro" "$TAG" /bin/bash -lc '
set -Eeuo pipefail
IMAGE=/build/image.raw
sgdisk -v "$IMAGE" >/build/gpt-verify.txt
p1_start=$(sgdisk -i 1 "$IMAGE" | awk "/First sector:/ {print \$3}")
p1_end=$(sgdisk -i 1 "$IMAGE" | awk "/Last sector:/ {print \$3}")
p2_start=$(sgdisk -i 2 "$IMAGE" | awk "/First sector:/ {print \$3}")
p2_end=$(sgdisk -i 2 "$IMAGE" | awk "/Last sector:/ {print \$3}")
for v in "$p1_start" "$p1_end" "$p2_start" "$p2_end"; do [[ "$v" =~ ^[0-9]+$ ]]; done
p1_count=$((p1_end-p1_start+1)); p2_count=$((p2_end-p2_start+1))
dd if="$IMAGE" of=/build/esp.img bs=512 skip="$p1_start" count="$p1_count" status=none
dd if="$IMAGE" of=/build/root.img bs=512 skip="$p2_start" count="$p2_count" status=none
mdir -i /build/esp.img ::/EFI/BOOT/BOOTX64.EFI >/build/efi-list.txt
e2fsck -fn /build/root.img >/build/ext4-check.txt 2>&1 || rc=$?
[ "${rc:-0}" -le 1 ]
debugfs -R "stat /etc/minitz/source.json" /build/root.img >/build/source-stat.txt 2>&1
debugfs -R "stat /usr/bin/minitz" /build/root.img >/build/launcher-stat.txt 2>&1
kernel=$(python3 -c "import json;print(json.load(open(\"/build.json\"))[\"kernel\"])")
debugfs -R "stat /boot/$kernel" /build/root.img >/build/kernel-stat.txt 2>&1
debugfs -R "cat /etc/minitz/source.json" /build/root.img 2>/dev/null >/build/source.json
python3 - <<PY
import json,os
m=json.load(open("/build/source.json")); b=json.load(open("/build.json"))
assert m["product"]=="MiniTZ OS"
assert m["base_os"]=="Ubuntu 26.04"
assert m["source_sha256"]==b["source_sha256"]==os.environ["SOURCE_SHA"]
assert m["bootable_disk_image"] is True
PY
'
python3 - "$IMAGE" "$STATE/build.json" "$WORK/validation.json" <<'PY'
import hashlib,json,os,sys
image,build_path,out=sys.argv[1:]
build=json.load(open(build_path))
h=hashlib.sha256()
with open(image,'rb') as f:
    for block in iter(lambda:f.read(8*1024*1024),b''):
        h.update(block)
result={**build,'schema':'minitz.boot_image_validation/v1','image_path':image,
 'image_sha256':h.hexdigest(),'image_bytes':os.path.getsize(image),
 'bootable_disk_image':True,'partition_table':'GPT','efi_system_partition':'PASS',
 'efi_bootloader_path':'/EFI/BOOT/BOOTX64.EFI','root_filesystem':'EXT4_PASS',
 'kernel_present':'PASS','source_identity_embedded':'PASS','image_boot_executed':False,
 'quality_verdict':'PASS'}
json.dump(result,open(out,'w'),sort_keys=True,indent=2)
print(json.dumps(result,sort_keys=True))
PY
PYTHONPATH="$REPO/src" python3 - "$REPO" "$SANDBOX" "$IMAGE" "$STATE/build.json" "$WORK/validation.json" <<'PYART'
import sys
from pathlib import Path
from minitz_os.boot_artifact import publish_validated_boot_artifact
publish_validated_boot_artifact(*(Path(value) for value in sys.argv[1:]))
PYART
