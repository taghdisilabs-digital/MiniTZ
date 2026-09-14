#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${MINITZ_DEVELOPMENT_ROOT:?Canonical source resource is required}"
export PYTHONPATH="$ROOT/ops/local-ai${PYTHONPATH:+:$PYTHONPATH}"
exec "${MINITZ_PRODUCTION_PYTHON:-python3}" -c 'import sys; from minitz_codex_account_pool import router_main; raise SystemExit(router_main(sys.argv[1:]))' "$@"
