#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCHER="$ROOT_DIR/ops/local-ai/biella-ai-start.sh"
SATURN_MCP="$ROOT_DIR/ops/local-ai/biella-saturn-mcp.sh"
INSTALLER="$ROOT_DIR/ops/local-ai/install-biella-ai.sh"
CODEX_WRAPPER="$ROOT_DIR/ops/local-ai/biella-codex.sh"
MANIFEST="$ROOT_DIR/docs/project-state/BIELLA_LOCAL_AI_RUNTIME_MANIFEST_2026-09-04.yaml"

require_file() {
  [[ -f "$1" ]] || { echo "missing required artifact: $1" >&2; exit 1; }
}

require_literal() {
  local file="$1"
  local literal="$2"
  rg -F --quiet -- "$literal" "$file" || {
    echo "missing contract literal in $file: $literal" >&2
    exit 1
  }
}

forbid_literal() {
  local file="$1"
  local literal="$2"
  if rg -F --quiet -- "$literal" "$file"; then
    echo "forbidden runtime behavior in $file: $literal" >&2
    exit 1
  fi
}

require_file "$LAUNCHER"
require_file "$SATURN_MCP"
require_file "$INSTALLER"
require_file "$CODEX_WRAPPER"
require_file "$MANIFEST"

require_literal "$LAUNCHER" 'qwen3-coder-next:biella'
require_literal "$LAUNCHER" 'num_gpu'
require_literal "$LAUNCHER" 'num_ctx'
require_literal "$LAUNCHER" 'keep_alive'
require_literal "$LAUNCHER" 'CPU_RAM_TARGET_GIB=86'
require_literal "$LAUNCHER" 'SATURN_BASE_URL'
require_literal "$LAUNCHER" 'SATURN_TOKEN'
require_literal "$LAUNCHER" 'CLOUDFLARE_ACCOUNT_ID'
require_literal "$LAUNCHER" 'CLOUDFLARE_API_TOKEN'
require_literal "$LAUNCHER" 'CLOUDFLARE_TUNNEL_TOKEN'
require_literal "$LAUNCHER" 'account-api'
require_literal "$LAUNCHER" 'codex mcp'
require_literal "$LAUNCHER" '30 * 1024 * 1024 * 1024'
require_literal "$LAUNCHER" 'systemctl'
require_literal "$SATURN_MCP" 'saturn-mcp'
require_literal "$SATURN_MCP" 'SATURN_TOKEN'
require_literal "$INSTALLER" 'biella-ai-start'
require_literal "$CODEX_WRAPPER" 'runtime.env'
require_literal "$CODEX_WRAPPER" '--oss'
require_literal "$CODEX_WRAPPER" '--local-provider'
require_literal "$CODEX_WRAPPER" 'ollama'
require_literal "$CODEX_WRAPPER" '--dangerously-bypass-approvals-and-sandbox'
require_literal "$CODEX_WRAPPER" '--dangerously-bypass-hook-trust'
require_literal "$CODEX_WRAPPER" '--search'
require_literal "$MANIFEST" 'WEBSITE'
require_literal "$MANIFEST" 'ENGINE'
require_literal "$MANIFEST" 'GAMES'
require_literal "$MANIFEST" 'vllm: forbidden'
require_literal "$MANIFEST" 'model_download: forbidden'
require_literal "$MANIFEST" 'CLOUDFLARE_ACCOUNT_ID'
require_literal "$MANIFEST" 'CLOUDFLARE_API_TOKEN'

forbid_literal "$LAUNCHER" 'ollama pull'
forbid_literal "$LAUNCHER" 'vllm serve'
forbid_literal "$LAUNCHER" '<YOUR_TOKEN>'
forbid_literal "$SATURN_MCP" '<YOUR_TOKEN>'

echo "local AI runtime contract: PASS"
