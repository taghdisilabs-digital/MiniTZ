#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT_DIR/ops/workstation/biella"
LIB="$ROOT_DIR/ops/workstation/biella-lib.sh"
INSTALLER="$ROOT_DIR/ops/workstation/install-biella-workstation.sh"
SERVICE="$ROOT_DIR/ops/workstation/biella-ollama.service"
RESIDENCY="$ROOT_DIR/ops/workstation/biella-qwen-residency.sh"
RESIDENCY_SERVICE="$ROOT_DIR/ops/workstation/biella-qwen-residency.service"
POLICY="$ROOT_DIR/ops/workstation/AGENTS.md"
PROVIDERS="$ROOT_DIR/ops/workstation/biella-provider-check.sh"
CONFIGURER="$ROOT_DIR/ops/workstation/biella-provider-configure.sh"

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
for f in "$CLI" "$LIB" "$INSTALLER" "$SERVICE" "$RESIDENCY" "$RESIDENCY_SERVICE" "$POLICY" "$PROVIDERS" "$CONFIGURER"; do require_file "$f"; done

for cmd in up down status doctor providers configure resource modal logs cleanup; do
  require_literal "$CLI" "$cmd"
done
for obsolete_case in 'agent)' 'work)' 'codex)' 'model)' 'luna)' 'astra)'; do
  forbid_literal "$CLI" "$obsolete_case"
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
require_literal "$POLICY" 'Codex chooses local Qwen'
require_literal "$POLICY" 'one external provider'
require_literal "$POLICY" 'free/trial/prepaid'
require_literal "$POLICY" 'paid external Resources'
require_literal "$POLICY" 'biella resource route'
require_literal "$POLICY" 'Never print secret values'
require_literal "$INSTALLER" '/root/.codex/AGENTS.md'
require_literal "$CLI" 'readlink -f'
require_literal "$PROVIDERS" 'api.groq.com/openai/v1/models'
require_literal "$PROVIDERS" 'api.cerebras.ai/v1/models'
require_literal "$PROVIDERS" 'openrouter.ai/api/v1/models'
require_literal "$PROVIDERS" 'api.mistral.ai/v1/models'
require_literal "$PROVIDERS" 'api.tavily.com/usage'
require_literal "$PROVIDERS" 'generativelanguage.googleapis.com/v1beta/openai/models'
require_literal "$CONFIGURER" 'GROQ_API_KEY'
require_literal "$CONFIGURER" 'CEREBRAS_API_KEY'
require_literal "$CONFIGURER" 'OPENROUTER_API_KEY'
require_literal "$CONFIGURER" 'MISTRAL_API_KEY'
require_literal "$CONFIGURER" 'TAVILY_API_KEY'
require_literal "$INSTALLER" 'biella-provider-configure'
require_literal "$CLI" 'Docker:'
require_literal "$LIB" 'llm-router'
require_literal "$LIB" 'runuser -u ollama -- env'
require_literal "$LIB" 'pgrep -P'
require_literal "$LIB" 'biella_find_exact_argv'
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

# Production routing must not start before local Qwen residency is confirmed.
PRODUCTION_SERVICE="$ROOT_DIR/ops/local-ai/biella-codex-production.service"
require_file "$PRODUCTION_SERVICE"
require_literal "$PRODUCTION_SERVICE" 'After=network-online.target docker.service project-sandbox-broker.service biella-ollama.service biella-qwen-residency.service'
require_literal "$PRODUCTION_SERVICE" 'ExecStartPre=/usr/local/lib/biella-workstation/biella-qwen-ready.sh'

require_literal "$SERVICE" 'ExecCondition=+/usr/local/lib/biella-ai/biella_customer_handoff.py guard-production'
require_literal "$RESIDENCY_SERVICE" 'ExecCondition=+/usr/local/lib/biella-ai/biella_customer_handoff.py guard-production'
require_literal "$PRODUCTION_SERVICE" 'ExecCondition=/usr/local/lib/biella-ai/biella_customer_handoff.py guard-production'
require_literal "$PRODUCTION_SERVICE" 'RequiresMountsFor=/mnt/biella-extra'
require_file "$ROOT_DIR/ops/workstation/biella-qwen-ready.sh"
require_literal "$ROOT_DIR/ops/workstation/biella-qwen-ready.sh" '/api/ps'
require_literal "$ROOT_DIR/ops/workstation/biella-qwen-ready.sh" 'qwen3-coder-next:biella'
require_literal "$ROOT_DIR/ops/workstation/install-biella-workstation.sh" 'biella-qwen-ready.sh'
