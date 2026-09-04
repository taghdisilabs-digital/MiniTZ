#!/usr/bin/env bash
set -Eeuo pipefail

readonly SELF="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd -P)"
readonly CONTRACT="${BIELLA_WORK_CONTRACT:-$SCRIPT_DIR/biella-work-contract.md}"
readonly LOCAL_AGENT="${BIELLA_LOCAL_AGENT:-/usr/local/bin/biella-local-agent}"

[[ -f "$CONTRACT" ]] || { printf 'Missing Biella work contract: %s\n' "$CONTRACT" >&2; exit 1; }
[[ -x "$LOCAL_AGENT" ]] || { printf 'Missing Biella local agent: %s\n' "$LOCAL_AGENT" >&2; exit 1; }

if [[ $# -eq 0 ]]; then
  exec "$LOCAL_AGENT"
fi

task="$*"
out="$(mktemp /tmp/biella-work-last.XXXXXX)"
log="$(mktemp /tmp/biella-work-log.XXXXXX)"
trap 'rm -f -- "$out" "$log"' EXIT
prompt="$(cat "$CONTRACT")

Operator task:
$task"

if "$LOCAL_AGENT" exec --color never --output-last-message "$out" "$prompt" </dev/null >"$log" 2>&1; then
  cat "$out"
else
  rc=$?
  tail -n 60 "$log" >&2
  exit "$rc"
fi
