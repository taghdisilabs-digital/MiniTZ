#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT_DIR/ops/workstation/biella-provider-configure.sh"
TMP="$(mktemp -d /tmp/biella-provider-config.XXXXXX)"
trap 'rm -rf -- "$TMP"' EXIT
RUNTIME="$TMP/runtime.env"
printf 'GROQ_API_KEY=%q\n' 'preserve-me' > "$RUNTIME"
chmod 600 "$RUNTIME"

set +e
OUTPUT="$(python3 -c 'print("\n" * 26, end="")' | BIELLA_AI_RUNTIME_ENV="$RUNTIME" bash "$CONFIG" 2>&1)"
RC=$?
set -e

[[ "$RC" -eq 0 ]] || { printf '%s\n' "$OUTPUT" >&2; exit 1; }
[[ "$(stat -c '%a' "$RUNTIME")" == 600 ]]
grep -F --quiet -- 'GROQ_API_KEY=preserve-me' "$RUNTIME"
grep -F --quiet -- 'Provider configuration updated.' <<< "$OUTPUT"
echo 'workstation provider configure smoke: PASS'
