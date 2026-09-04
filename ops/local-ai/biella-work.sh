#!/usr/bin/env bash
set -Eeuo pipefail

readonly SELF="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd -P)"
readonly CONTRACT="${BIELLA_WORK_CONTRACT:-$SCRIPT_DIR/biella-work-contract.md}"
readonly FULL_CONTROLLER="${BIELLA_WORK_CONTROLLER:-/usr/local/bin/biella-local-agent}"

[[ -f "$CONTRACT" ]] || { printf 'Missing Biella work contract: %s\n' "$CONTRACT" >&2; exit 1; }
[[ -x "$FULL_CONTROLLER" ]] || { printf 'Missing Biella low-noise controller: %s\n' "$FULL_CONTROLLER" >&2; exit 1; }

if [[ $# -eq 0 ]]; then
  exec "$FULL_CONTROLLER"
fi

task="$*"
out="$(mktemp /tmp/biella-work-last.XXXXXX)"
log="$(mktemp /tmp/biella-work-log.XXXXXX)"
trap 'rm -f -- "$out" "$log"' EXIT
prompt="$(cat "$CONTRACT")

Operator task:
$task"

if "$FULL_CONTROLLER" exec --color never --output-last-message "$out" "$prompt" </dev/null >"$log" 2>&1; then
  cat "$out"
else
  rc=$?
  tail -n 60 "$log" >&2
  exit "$rc"
fi
