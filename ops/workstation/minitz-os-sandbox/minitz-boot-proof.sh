#!/bin/sh
set -eu

/usr/bin/minitz source >/run/minitz-source.json
/usr/bin/minitz resource status >/run/minitz-resource.json
/usr/bin/minitz dashboard --json >/run/minitz-dashboard.json
/usr/bin/minitz doctor --json >/run/minitz-doctor.json

/usr/bin/python3 - <<'PY' >/dev/ttyS0
import json
from pathlib import Path

source=json.loads(Path('/run/minitz-source.json').read_text())
resources=json.loads(Path('/run/minitz-resource.json').read_text())
surface=json.loads(Path('/run/minitz-dashboard.json').read_text())
doctor=json.loads(Path('/run/minitz-doctor.json').read_text())
assert source.get('verified') is True and source.get('product') == 'MiniTZ OS'
assert resources.get('schema') == 'minitz.provider_registry/v1'
assert surface.get('schema') == 'minitz.operator-surface/v1' and surface.get('product') == 'MiniTZ OS'
assert doctor.get('schema') == 'minitz.doctor/v1'
sha=source['source_sha256']
print(f"MINITZ_BOOT_RESOURCE_OK providers={len(resources.get('providers', []))}")
print(f"MINITZ_BOOT_SURFACE_OK sections={len(surface.get('sections', []))} capabilities={len(surface.get('capabilities', []))}")
print(f"MINITZ_BOOT_DOCTOR_OK checks={doctor.get('check_count', 0)} availability={doctor.get('overall_availability', 'UNKNOWN')}")
print(f"MINITZ_BOOT_OK source_sha256={sha}")
PY
