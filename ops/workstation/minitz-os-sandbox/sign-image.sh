#!/usr/bin/env bash
set -Eeuo pipefail

SANDBOX=${MINITZ_OS_SANDBOX_ROOT:-/root/attached-storage/minitz-os-sandbox}
REPO="$SANDBOX/workspace/repo"
STATE="$SANDBOX/state/image-build"
IMAGE=${1:?image path required}
RECEIPT=${2:-$STATE/validation/image-signature.json}
KEY_FILE=${MINITZ_UPDATE_SIGNING_KEY_FILE:?MINITZ_UPDATE_SIGNING_KEY_FILE is required}
KEY_REF=${MINITZ_UPDATE_SIGNING_KEY_REF:-credential://minitz/update-signing-key}

test -f "$IMAGE"
test -f "$STATE/build.json"
test -f "$KEY_FILE"
mkdir -p "$(dirname "$RECEIPT")"

PYTHONPATH="$REPO/src" python3 - "$IMAGE" "$STATE/build.json" "$KEY_FILE" "$RECEIPT" "$KEY_REF" <<'PY'
import json
import sys
from pathlib import Path

from minitz_os.source import sign_release, verify_signed_release

image_path, build_path, key_path, receipt_path = map(Path, sys.argv[1:5])
key_ref = sys.argv[5]
build = json.loads(build_path.read_text(encoding="utf-8"))
key = key_path.read_bytes()
signed = sign_release(image_path, build["source_sha256"], key, key_ref=key_ref)
verified = verify_signed_release(signed, image_path, key)
receipt = {
    **signed,
    "artifact_kind": "BOOTABLE_DISK_IMAGE",
    "bootable_disk_image": True,
    "verified_after_signing": verified["verified"],
}
receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "receipt_path": str(receipt_path),
    "artifact_sha256": receipt["artifact_sha256"],
    "source_sha256": receipt["source_sha256"],
    "key_ref": receipt["key_ref"],
    "verified_after_signing": receipt["verified_after_signing"],
}, sort_keys=True))
PY
