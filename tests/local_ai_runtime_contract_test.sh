#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCHER="$ROOT_DIR/ops/local-ai/minitz-ai-start.sh"
SATURN_MCP="$ROOT_DIR/ops/local-ai/minitz-saturn-mcp.sh"
INSTALLER="$ROOT_DIR/ops/local-ai/install-minitz-ai.sh"
CODEX_WRAPPER="$ROOT_DIR/ops/local-ai/minitz-codex.sh"
MANIFEST="$ROOT_DIR/docs/project-state/MINITZ_LOCAL_AI_RUNTIME_MANIFEST_2026-09-04.yaml"

require_file() { [[ -f "$1" ]] || { echo "missing required artifact: $1" >&2; exit 1; }; }
require_literal() { grep -Fq -- "$2" "$1" || { echo "missing contract literal in $1: $2" >&2; exit 1; }; }
forbid_literal() { ! grep -Fq -- "$2" "$1" || { echo "forbidden runtime behavior in $1: $2" >&2; exit 1; }; }

for f in "$LAUNCHER" "$SATURN_MCP" "$INSTALLER" "$CODEX_WRAPPER" "$MANIFEST"; do require_file "$f"; done

require_literal "$LAUNCHER" 'qwen3-coder-next:minitz'
require_literal "$LAUNCHER" 'num_gpu'
require_literal "$LAUNCHER" 'num_ctx'
require_literal "$LAUNCHER" 'keep_alive'
require_literal "$SATURN_MCP" 'SATURN_TOKEN'
require_literal "$CODEX_WRAPPER" 'runtime.env'
require_literal "$CODEX_WRAPPER" 'CODEX_HOME="/root/.codex"'
require_literal "$CODEX_WRAPPER" '--dangerously-bypass-approvals-and-sandbox'
require_literal "$CODEX_WRAPPER" 'shell_environment_policy.inherit'
require_literal "$CODEX_WRAPPER" '--search'
forbid_literal "$CODEX_WRAPPER" '--oss'
forbid_literal "$CODEX_WRAPPER" '--local-provider'
forbid_literal "$CODEX_WRAPPER" 'qwen3-coder-next:minitz'
require_literal "$INSTALLER" '/usr/local/bin/minitz-codex'
require_literal "$MANIFEST" 'codex_wrapper:'
require_literal "$MANIFEST" 'local_qwen:'
forbid_literal "$LAUNCHER" 'ollama pull'
forbid_literal "$LAUNCHER" 'vllm serve'

for obsolete in \
  "$ROOT_DIR/ops/local-ai/minitz-local-agent.sh" \
  "$ROOT_DIR/ops/local-ai/minitz-work.sh" \
  "$ROOT_DIR/ops/local-ai/minitz-work-contract.md" \
  "$ROOT_DIR/ops/local-ai/minitz-model.sh" \
  "$ROOT_DIR/ops/local-ai/minitz-luna.sh" \
  "$ROOT_DIR/ops/local-ai/minitz-astra.sh"; do
  [[ ! -e "$obsolete" ]] || { echo "obsolete controller source remains: $obsolete" >&2; exit 1; }
done

bash -n "$LAUNCHER"
bash -n "$SATURN_MCP"
bash -n "$INSTALLER"
bash -n "$CODEX_WRAPPER"
echo 'local AI runtime contract: PASS'
