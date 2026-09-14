#!/usr/bin/env bash
set -Eeuo pipefail
readonly REPO="${MINITZ_REPO_ROOT:-/root/attached-storage/minitz-os-sandbox/workspace/repo}"
readonly RUNTIME="$REPO/ops/workstation/minitz-os-sandbox/runtime.sh"
[[ -x "$RUNTIME" ]] || { printf 'MiniTZ runtime launcher unavailable: %s\n' "$RUNTIME" >&2; exit 1; }
case "${1:-on}" in
  on) exec "$RUNTIME" on ;;
  status) exec "$RUNTIME" status ;;
  *) printf 'usage: minitz-ai-start.sh {on|status}\n' >&2; exit 2 ;;
esac
