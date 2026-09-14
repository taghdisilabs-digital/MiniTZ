#!/usr/bin/env bash
set -Eeuo pipefail
BUILD=${1:-/build}
ROOTFS="$BUILD/rootfs"
SOURCE_SHA=${SOURCE_SHA:?SOURCE_SHA required}
IMAGE="$BUILD/MiniTZ-OS-${SOURCE_SHA:0:16}.raw"
KERNEL=$(find "$ROOTFS/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort -V | tail -1)
INITRD=$(find "$ROOTFS/boot" -maxdepth 1 -type f -name 'initrd.img-*' | sort -V | tail -1)
test -s "$KERNEL"
test -s "$INITRD"
used=$(du -sx --block-size=1 "$ROOTFS" | awk '{print $1}')
step=$((256*1024*1024))
reserve=$((768*1024*1024))
root_bytes=$((used+reserve))
root_bytes=$(((root_bytes+step-1)/step*step))
[ "$root_bytes" -ge $((1536*1024*1024)) ] || root_bytes=$((1536*1024*1024))
truncate -s "$root_bytes" "$BUILD/rootfs.img"
mkfs.ext4 -q -F -L MINITZROOT -d "$ROOTFS" "$BUILD/rootfs.img"
truncate -s 128M "$BUILD/esp.img"
mkfs.vfat -F 32 -n MINITZEFI "$BUILD/esp.img" >/dev/null
cat >"$BUILD/grub.cfg" <<CFG
insmod part_gpt
insmod ext2
search --no-floppy --label MINITZROOT --set=root
linux /boot/$(basename "$KERNEL") root=LABEL=MINITZROOT ro rootwait console=ttyS0,115200n8 systemd.show_status=1
initrd /boot/$(basename "$INITRD")
boot
CFG
grub-mkstandalone -O x86_64-efi -o "$BUILD/BOOTX64.EFI" "boot/grub/grub.cfg=$BUILD/grub.cfg"
mmd -i "$BUILD/esp.img" ::/EFI ::/EFI/BOOT
mcopy -i "$BUILD/esp.img" "$BUILD/BOOTX64.EFI" ::/EFI/BOOT/BOOTX64.EFI
disk_bytes=$((root_bytes+384*1024*1024))
disk_bytes=$(((disk_bytes+step-1)/step*step))
truncate -s "$disk_bytes" "$IMAGE"
sgdisk --clear --new=1:2048:+128M --typecode=1:ef00 --change-name=1:MINITZEFI \
  --new=2:0:0 --typecode=2:8300 --change-name=2:MINITZROOT "$IMAGE" >/dev/null
p1=$(sgdisk -i 1 "$IMAGE" | awk '/First sector:/ {print $3}')
p2=$(sgdisk -i 2 "$IMAGE" | awk '/First sector:/ {print $3}')
dd if="$BUILD/esp.img" of="$IMAGE" bs=512 seek="$p1" conv=notrunc status=none
dd if="$BUILD/rootfs.img" of="$IMAGE" bs=512 seek="$p2" conv=notrunc status=none
sync
python3 - "$BUILD/build.json" "$IMAGE" "$SOURCE_SHA" "$root_bytes" "$KERNEL" <<'PY'
import hashlib,json,os,sys
out,image,source,root_bytes,kernel=sys.argv[1:]
h=hashlib.sha256()
with open(image,'rb') as f:
    for block in iter(lambda:f.read(8*1024*1024),b''):
        h.update(block)
json.dump({'schema':'minitz.boot_image_build/v1','product':'MiniTZ OS',
 'base_os':'Ubuntu 26.04','artifact_kind':'BOOTABLE_DISK_IMAGE','bootable_disk_image':True,
 'source_sha256':source,'image_path':image,'image_sha256':h.hexdigest(),
 'image_bytes':os.path.getsize(image),'rootfs_bytes':int(root_bytes),
 'kernel':os.path.basename(kernel)},open(out,'w'),sort_keys=True,indent=2)
PY
printf '%s\n' "$IMAGE"
