#!/usr/bin/env bash
set -Eeuo pipefail
CREDENTIAL_ENV="${MINITZ_CREDENTIAL_ENV:-/resources/credentials/runtime.env}"
if [[ -f "$CREDENTIAL_ENV" ]]; then
  set -a
  source "$CREDENTIAL_ENV"
  set +a
fi
exec "${MINITZ_PRODUCTION_PYTHON:-python3}" "${MINITZ_DEVELOPMENT_ROOT:?}/ops/workstation/minitz-resource.py" "$@"
