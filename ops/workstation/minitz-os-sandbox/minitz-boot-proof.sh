#!/bin/sh
set -eu

/usr/bin/minitz source >/run/minitz-source.json
sha=$(/usr/bin/python3 -c 'import json; print(json.load(open("/run/minitz-source.json"))["source_sha256"])')
printf 'MINITZ_BOOT_OK source_sha256=%s\n' "$sha" >/dev/ttyS0
