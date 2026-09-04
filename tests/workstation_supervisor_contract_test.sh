#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT_DIR/ops/workstation/biella"
LIB="$ROOT_DIR/ops/workstation/biella-lib.sh"
INSTALLER="$ROOT_DIR/ops/workstation/install-biella-workstation.sh"

require_file() {
  [[ -f "$1" ]] || { echo "missing required artifact: $1" >&2; exit 1; }
}

require_literal() {
  local file="$1" literal="$2"
  rg -F --quiet -- "$literal" "$file" || {
    echo "missing contract literal in $file: $literal" >&2
    exit 1
  }
}

forbid_literal() {
  local file="$1" literal="$2"
  ! rg -F --quiet -- "$literal" "$file" || {
    echo "forbidden literal in $file: $literal" >&2
    exit 1
  }
}
for f in "$CLI" "$LIB" "$INSTALLER"; do require_file "$f"; done

for cmd in up down status doctor agent codex providers modal logs cleanup; do
  require_literal "$CLI" "$cmd"
done

require_literal "$LIB" '/root/.config/biella-ai/runtime.env'
require_literal "$LIB" '/mnt/biella-extra/biella-runtime'
require_literal "$LIB" 'qwen3-coder-next:biella'
require_literal "$LIB" '127.0.0.1:11434'
require_literal "$INSTALLER" '/usr/local/bin/biella'
require_literal "$INSTALLER" 'root'
forbid_literal "$CLI" 'ollama pull'
forbid_literal "$LIB" 'ollama pull'
forbid_literal "$INSTALLER" 'ollama pull'

bash -n "$CLI"
bash -n "$LIB"
bash -n "$INSTALLER"

echo 'workstation supervisor contract: PASS'
