#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT_DIR/ops/workstation/minitz-workstation"
LIB="$ROOT_DIR/ops/workstation/minitz-lib.sh"
INSTALLER="$ROOT_DIR/ops/workstation/install-minitz-workstation.sh"
SERVICE="$ROOT_DIR/ops/workstation/minitz-ollama.service"
RESIDENCY="$ROOT_DIR/ops/workstation/minitz-qwen-residency.sh"
RESIDENCY_SERVICE="$ROOT_DIR/ops/workstation/minitz-qwen-residency.service"
POLICY="$ROOT_DIR/ops/workstation/AGENTS.md"
PRODUCTION_SERVICE="$ROOT_DIR/ops/local-ai/minitz-production.service"
require_file(){ [[ -f "$1" ]] || { echo "missing required artifact: $1" >&2; exit 1; }; }
require_literal(){ rg -F --quiet -- "$2" "$1" || { echo "missing contract literal in $1: $2" >&2; exit 1; }; }
forbid_literal(){ ! rg -F --quiet -- "$2" "$1" || { echo "forbidden literal in $1: $2" >&2; exit 1; }; }
for f in "$CLI" "$LIB" "$INSTALLER" "$SERVICE" "$RESIDENCY" "$RESIDENCY_SERVICE" "$POLICY" "$PRODUCTION_SERVICE"; do require_file "$f"; done
for cmd in up status doctor providers configure resource modal logs; do require_literal "$CLI" "$cmd"; done
require_literal "$LIB" '/root/attached-storage/minitz-os-sandbox/state/credentials/runtime.env'
require_literal "$LIB" 'qwen3-coder-next:minitz'
require_literal "$LIB" '127.0.0.1:11434'
require_literal "$INSTALLER" '/usr/local/bin/minitz-workstation'
require_literal "$INSTALLER" 'minitz-ollama.service'
require_literal "$INSTALLER" 'minitz-qwen-residency.service'
require_literal "$SERVICE" 'User=ollama'
require_literal "$SERVICE" 'OLLAMA_HOST=127.0.0.1:11434'
require_literal "$SERVICE" 'OLLAMA_MAX_LOADED_MODELS=2'
require_literal "$SERVICE" 'OLLAMA_KEEP_ALIVE=-1'
forbid_literal "$SERVICE" 'OLLAMA_NUM_PARALLEL='
require_literal "$RESIDENCY_SERVICE" 'MINITZ_QWEN_RESIDENCY_INTERVAL_SECONDS=5'
require_literal "$RESIDENCY_SERVICE" 'minitz-ollama.service'
require_literal "$POLICY" 'Local Qwen is a logic/code/calculation/comparison Resource'
require_literal "$POLICY" 'EXECUTOR_OWNS_ROUTINE_BLOCKER_RESOLUTION'
require_literal "$POLICY" 'RAW_IMAGE_BOOT_REQUIRES_EXPLICIT_OWNER_COMMAND'
require_literal "$PRODUCTION_SERVICE" 'RequiresMountsFor=/root/attached-storage'
require_literal "$PRODUCTION_SERVICE" 'minitz-qwen-residency.service'
forbid_literal "$PRODUCTION_SERVICE" 'Requires=minitz-ollama.service'
forbid_literal "$PRODUCTION_SERVICE" 'ExecStartPre=/usr/local/lib/minitz-workstation/minitz-qwen-ready.sh'
for f in "$CLI" "$LIB" "$INSTALLER" "$RESIDENCY"; do forbid_literal "$f" 'biella'; done
bash -n "$CLI"
bash -n "$LIB"
bash -n "$INSTALLER"
bash -n "$RESIDENCY"
echo 'workstation supervisor contract: PASS'
