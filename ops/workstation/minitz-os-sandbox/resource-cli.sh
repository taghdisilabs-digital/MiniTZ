#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${1:-}" == resource ]] || { printf 'Use the MiniTZ OS command surface.\n' >&2; exit 2; }
shift
CREDENTIAL_ENV="${BIELLA_AI_RUNTIME_ENV:-/resources/credentials/runtime.env}"
if [[ -f "$CREDENTIAL_ENV" ]]; then
  set -a
  source "$CREDENTIAL_ENV"
  set +a
fi
exec "${MINITZ_PRODUCTION_PYTHON:-python3}" "${MINITZ_DEVELOPMENT_ROOT:?}/ops/workstation/biella-resource.py" "$@"
