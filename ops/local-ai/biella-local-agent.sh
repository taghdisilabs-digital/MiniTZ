#!/usr/bin/env bash
set -Eeuo pipefail

readonly FULL_CONTROLLER="${BIELLA_CODEX_WRAPPER:-/usr/local/bin/biella-codex}"
[[ -x "$FULL_CONTROLLER" ]] || { printf 'Missing Biella Codex controller: %s\n' "$FULL_CONTROLLER" >&2; exit 1; }

# Fast local-first mode keeps the full provider environment and execution
# capabilities while avoiding local-model-incompatible reasoning and eager
# external plugin/MCP startup noise. Explicit provider tools remain available
# to child processes through the shared Biella runtime environment.
exec "$FULL_CONTROLLER" \
  -c 'model_reasoning_effort="none"' \
  -c 'mcp_servers.saturn.enabled=false' \
  --disable plugins \
  --disable apps \
  "$@"
