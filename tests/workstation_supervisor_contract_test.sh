#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT_DIR/ops/workstation/biella"
LIB="$ROOT_DIR/ops/workstation/biella-lib.sh"
INSTALLER="$ROOT_DIR/ops/workstation/install-biella-workstation.sh"
SERVICE="$ROOT_DIR/ops/workstation/biella-ollama.service"

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
for f in "$CLI" "$LIB" "$INSTALLER" "$SERVICE"; do require_file "$f"; done

for cmd in up down status doctor agent codex providers modal logs cleanup; do
  require_literal "$CLI" "$cmd"
done

require_literal "$LIB" '/root/.config/biella-ai/runtime.env'
require_literal "$LIB" '/mnt/biella-extra/biella-runtime'
require_literal "$LIB" 'qwen3-coder-next:biella'
require_literal "$LIB" '127.0.0.1:11434'
require_literal "$INSTALLER" '/usr/local/bin/biella'
require_literal "$INSTALLER" 'root'
require_literal "$SERVICE" 'User=ollama'
require_literal "$SERVICE" 'OLLAMA_HOST=127.0.0.1:11434'
require_literal "$SERVICE" 'OLLAMA_CONTEXT_LENGTH=16384'
require_literal "$SERVICE" 'OLLAMA_NUM_PARALLEL=1'
require_literal "$SERVICE" 'OLLAMA_MAX_LOADED_MODELS=1'
require_literal "$SERVICE" 'OLLAMA_FLASH_ATTENTION=1'
require_literal "$SERVICE" 'OLLAMA_KV_CACHE_TYPE=q8_0'
require_literal "$SERVICE" 'OLLAMA_KEEP_ALIVE=-1'
require_literal "$LIB" '/v1/responses'
require_literal "$LIB" '30 * 1024 * 1024 * 1024'
forbid_literal "$CLI" 'ollama pull'
forbid_literal "$LIB" 'ollama pull'
forbid_literal "$INSTALLER" 'ollama pull'

bash -n "$CLI"
bash -n "$LIB"
bash -n "$INSTALLER"

echo 'workstation supervisor contract: PASS'
