#!/usr/bin/env bash
set -Eeuo pipefail
SANDBOX=${MINITZ_OS_SANDBOX_ROOT:-/root/attached-storage/minitz-os-sandbox}
REPO="$SANDBOX/workspace/repo"
STATE="$SANDBOX/state/image-build"
OUTPUT=${1:-$SANDBOX/output/images}
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    exec "$REPO/ops/workstation/minitz-os-sandbox/build-image-local.sh" "$@"
fi
mkdir -p "$STATE" "$OUTPUT"
rm -rf "$STATE/context" "$STATE/rootfs"
mkdir -p "$STATE/context/source" "$STATE/rootfs"
PYTHONPATH="$REPO/src" python3 - "$REPO" "$STATE/context" <<'PY'
import json,shutil,sys
from pathlib import Path
from minitz_os.source import source_manifest,canonical,verify_source
root=Path(sys.argv[1]).resolve()
context=Path(sys.argv[2]).resolve()
manifest=source_manifest(root)
for rel in manifest['files']:
    src=root/rel
    dst=context/'source'/rel
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
verify_source(context/'source',manifest)
if source_manifest(root)['source_sha256'] != manifest['source_sha256']:
    raise SystemExit('MiniTZ source changed during image-source staging')
(context/'source.json').write_bytes(canonical(manifest)+b'\n')
print(manifest['source_sha256'])
PY
SOURCE_SHA=$(python3 -c 'import json;print(json.load(open("'$STATE'/context/source.json"))["source_sha256"])')
TAG="minitz-os-rootfs:${SOURCE_SHA:0:16}"
docker build -q -f "$REPO/ops/workstation/minitz-os-sandbox/ImageRootfs.Dockerfile" \
    -t "$TAG" "$STATE/context" >/dev/null
CID=$(docker create "$TAG" /bin/true)
trap 'docker rm -f "$CID" >/dev/null 2>&1 || true' EXIT
docker export "$CID" -o "$STATE/rootfs.tar"
docker rm "$CID" >/dev/null
CID=''
tar -xf "$STATE/rootfs.tar" -C "$STATE/rootfs"
cp "$REPO/ops/workstation/minitz-os-sandbox/image-layout.sh" "$STATE/image-layout.sh"
chmod +x "$STATE/image-layout.sh"
docker run --rm -e SOURCE_SHA="$SOURCE_SHA" -v "$STATE:/build" "$TAG" \
    /bin/bash /build/image-layout.sh /build
IMAGE="$STATE/MiniTZ-OS-${SOURCE_SHA:0:16}.raw"
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
printf '%s\n' "$TAG" >"$STATE/rootfs-image-tag"
printf '%s\n' "$OUTPUT_IMAGE"
