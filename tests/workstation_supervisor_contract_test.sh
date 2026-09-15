#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT_DIR/ops/workstation/minitz"
LIB="$ROOT_DIR/ops/workstation/minitz-lib.sh"
INSTALLER="$ROOT_DIR/ops/workstation/install-minitz-workstation.sh"
SERVICE="$ROOT_DIR/ops/workstation/minitz-ollama.service"
RESIDENCY="$ROOT_DIR/ops/workstation/minitz-qwen-residency.sh"
RESIDENCY_SERVICE="$ROOT_DIR/ops/workstation/minitz-qwen-residency.service"
GPU_POLICY="$ROOT_DIR/ops/workstation/minitz-gpu-residency.json"
POLICY="$ROOT_DIR/ops/workstation/AGENTS.md"
PROVIDERS="$ROOT_DIR/ops/workstation/minitz-provider-check.sh"
CONFIGURER="$ROOT_DIR/ops/workstation/minitz-provider-configure.sh"

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
for f in "$CLI" "$LIB" "$INSTALLER" "$SERVICE" "$RESIDENCY" "$RESIDENCY_SERVICE" "$GPU_POLICY" "$POLICY" "$PROVIDERS" "$CONFIGURER"; do require_file "$f"; done

for cmd in up down status doctor providers configure resource modal logs cleanup; do
  require_literal "$CLI" "$cmd"
done
for obsolete_case in 'agent)' 'work)' 'codex)' 'model)' 'luna)' 'astra)'; do
  forbid_literal "$CLI" "$obsolete_case"
done

require_literal "$LIB" '/root/.config/minitz-ai/runtime.env'
require_literal "$LIB" '/mnt/minitz-extra/minitz-runtime'
require_literal "$LIB" 'qwen3-coder-next:minitz'
require_literal "$LIB" '127.0.0.1:11434'
require_literal "$INSTALLER" '/usr/local/bin/minitz'
require_literal "$INSTALLER" 'root'
require_literal "$SERVICE" 'User=ollama'
require_literal "$SERVICE" 'OLLAMA_HOST=127.0.0.1:11434'
require_literal "$SERVICE" 'OLLAMA_CONTEXT_LENGTH=16384'
forbid_literal "$SERVICE" 'OLLAMA_NUM_PARALLEL='
require_literal "$SERVICE" 'OLLAMA_MAX_LOADED_MODELS=2'
require_literal "$SERVICE" 'OLLAMA_FLASH_ATTENTION=1'
require_literal "$SERVICE" 'OLLAMA_KV_CACHE_TYPE=q8_0'
require_literal "$SERVICE" 'OLLAMA_KEEP_ALIVE=-1'
require_literal "$LIB" '/v1/responses'
require_literal "$POLICY" 'Local Qwen is a logic/code/calculation/comparison Resource'
require_literal "$POLICY" 'Configured eligible Resources may be used automatically'
require_literal "$POLICY" 'provider backoff'
require_literal "$POLICY" 'Route by capability'
require_literal "$POLICY" 'Never reproduce raw secrets'
require_literal "$INSTALLER" '/root/.codex/AGENTS.md'
require_literal "$INSTALLER" 'minitz-gpu-residency.json'
require_literal "$GPU_POLICY" '"minitz_admission_gate": false'
require_literal "$GPU_POLICY" '"local_gpu_full_capability": true'
forbid_literal "$GPU_POLICY" 'required_free_vram_mib'
forbid_literal "$GPU_POLICY" 'max_vram_mib'
require_literal "$INSTALLER" 'ollama_active'
require_literal "$INSTALLER" 'qwen_active'
require_literal "$CLI" 'readlink -f'
require_literal "$PROVIDERS" 'api.groq.com/openai/v1/models'
require_literal "$PROVIDERS" 'api.cerebras.ai/v1/models'
require_literal "$PROVIDERS" 'openrouter.ai/api/v1/models'
require_literal "$PROVIDERS" 'api.mistral.ai/v1/models'
require_literal "$PROVIDERS" 'api.tavily.com/usage'
require_literal "$PROVIDERS" 'Gemini: DISABLED (owner excluded; no network probe)'
forbid_literal "$PROVIDERS" 'generativelanguage.googleapis.com/v1beta/openai/models'
require_literal "$CONFIGURER" 'GROQ_API_KEY'
require_literal "$CONFIGURER" 'CEREBRAS_API_KEY'
require_literal "$CONFIGURER" 'OPENROUTER_API_KEY'
require_literal "$CONFIGURER" 'MISTRAL_API_KEY'
require_literal "$CONFIGURER" 'TAVILY_API_KEY'
require_literal "$INSTALLER" 'minitz-provider-configure'
require_literal "$CLI" 'Docker:'
require_literal "$LIB" 'llm-router'
require_literal "$LIB" 'runuser -u ollama -- env'
require_literal "$LIB" 'pgrep -P'
require_literal "$LIB" 'minitz_find_exact_argv'
forbid_literal "$LIB" 'pgrep -f -- "$signature"'
require_literal "$LIB" 'http.server 61374'
require_literal "$LIB" 'http.server 81374'
require_literal "$LIB" 'http://127.0.0.1:61374'
forbid_literal "$CLI" 'ollama pull'
forbid_literal "$LIB" 'ollama pull'
forbid_literal "$INSTALLER" 'ollama pull'
forbid_literal "$PROVIDERS" 'curl -sS'

bash -n "$CLI"
bash -n "$LIB"
bash -n "$INSTALLER"

echo 'workstation supervisor contract: PASS'

# Production must not depend on optional local Qwen residency.
PRODUCTION_SERVICE="$ROOT_DIR/ops/local-ai/minitz-production.service"
require_file "$PRODUCTION_SERVICE"
forbid_literal "$PRODUCTION_SERVICE" 'Requires=minitz-ollama.service'
forbid_literal "$PRODUCTION_SERVICE" 'ExecStartPre=/usr/local/lib/minitz-workstation/minitz-qwen-ready.sh'

forbid_literal "$SERVICE" 'guard-production'
forbid_literal "$RESIDENCY_SERVICE" 'guard-production'
forbid_literal "$PRODUCTION_SERVICE" 'guard-production'
require_literal "$PRODUCTION_SERVICE" 'RequiresMountsFor=/mnt/minitz-extra'
require_file "$ROOT_DIR/ops/workstation/minitz-qwen-ready.sh"
require_literal "$ROOT_DIR/ops/workstation/minitz-qwen-ready.sh" '/api/ps'
require_literal "$ROOT_DIR/ops/workstation/minitz-qwen-ready.sh" 'qwen3-coder-next:minitz'
require_literal "$ROOT_DIR/ops/workstation/install-minitz-workstation.sh" 'minitz-qwen-ready.sh'
