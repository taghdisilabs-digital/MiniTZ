#!/usr/bin/env bash
set -Eeuo pipefail

readonly FULL_CONTROLLER="${BIELLA_CODEX_WRAPPER:-/usr/local/bin/biella-codex}"
[[ -x "$FULL_CONTROLLER" ]] || { printf 'Missing Biella Codex controller: %s\n' "$FULL_CONTROLLER" >&2; exit 1; }

# Fast local-first mode: keep the full provider environment and execution
# capabilities, but do not eagerly initialize Saturn MCP for every session.
exec "$FULL_CONTROLLER" -c 'mcp_servers.saturn.enabled=false' "$@"
