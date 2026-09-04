#!/usr/bin/env bash
set -Eeuo pipefail

readonly FULL_CONTROLLER="${BIELLA_CODEX_WRAPPER:-/usr/local/bin/biella-codex}"
readonly SELF="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd -P)"
readonly QWEN_CATALOG="${BIELLA_QWEN_CODEX_CATALOG:-$SCRIPT_DIR/qwen-codex-model-catalog.json}"
[[ -x "$FULL_CONTROLLER" ]] || { printf 'Missing Biella Codex controller: %s\n' "$FULL_CONTROLLER" >&2; exit 1; }
[[ -f "$QWEN_CATALOG" ]] || { printf 'Missing Qwen Codex model catalog: %s\n' "$QWEN_CATALOG" >&2; exit 1; }

# Fast local-first mode keeps the full provider environment and execution
# capabilities while avoiding local-model-incompatible reasoning and eager
# external plugin/MCP startup noise. Explicit provider tools remain available
# to child processes through the shared Biella runtime environment.
export BIELLA_CODEX_DISABLE_HOOKS=1

exec "$FULL_CONTROLLER" \
  -c "model_catalog_json=\"$QWEN_CATALOG\"" \
  -c 'model_reasoning_effort="none"' \
  -c 'mcp_servers.saturn.enabled=false' \
  --disable plugins \
  --disable apps \
  "$@"
