#!/usr/bin/env bash
set -Eeuo pipefail

readonly SELF="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SOURCE_ROOT="${MINITZ_SOURCE_ROOT:-$(cd "$(dirname "$SELF")/../.." && pwd)}"
readonly CLI_LINK="${MINITZ_CONNECTORS_CLI_LINK:-/usr/local/bin/minitz-connectors}"
readonly ENTRY="$SOURCE_ROOT/ops/connectors/reconcile.py"

[[ "$EUID" -eq 0 ]] || { printf 'Run MiniTZ connectors installer as root.\n' >&2; exit 1; }
[[ -f "$ENTRY" ]] || { printf 'MiniTZ connectors source missing: %s\n' "$ENTRY" >&2; exit 1; }
chmod 0755 "$ENTRY" "$SOURCE_ROOT/ops/connectors/minitz-private-secret-verifier.py"
if [[ -e "$CLI_LINK" || -L "$CLI_LINK" ]]; then
  [[ -L "$CLI_LINK" ]] || { printf 'Refusing to replace unrelated path: %s\n' "$CLI_LINK" >&2; exit 1; }
  target="$(readlink "$CLI_LINK")"
  [[ "$target" == "$ENTRY" ]] || { printf 'Refusing to replace unrelated path: %s\n' "$CLI_LINK" >&2; exit 1; }
  rm -f -- "$CLI_LINK"
fi
ln -s "$ENTRY" "$CLI_LINK"
printf 'Installed MiniTZ connectors command from canonical source.\n'
