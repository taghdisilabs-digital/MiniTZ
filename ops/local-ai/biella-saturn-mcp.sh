#!/usr/bin/env bash
set -Eeuo pipefail

readonly RUNTIME_ENV="${BIELLA_AI_RUNTIME_ENV:-/root/.config/biella-ai/runtime.env}"
readonly SATURN_PLUGIN_SPEC="saturn-mcp @ git+https://github.com/saturncloud/claude-plugin.git@main#subdirectory=plugins/saturn-cloud"

[[ "$EUID" -eq 0 ]] || {
  printf 'Biella Saturn MCP requires the root-only runtime environment.\n' >&2
  exit 1
}
[[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]] || {
  printf 'Biella Saturn MCP runtime credentials are not configured.\n' >&2
  exit 1
}
[[ "$(stat -c '%u' "$RUNTIME_ENV")" == "0" && "$(stat -c '%a' "$RUNTIME_ENV")" == "600" ]] || {
  printf 'Biella Saturn MCP runtime environment must be root-owned mode 0600.\n' >&2
  exit 1
}

set -a
# shellcheck disable=SC1090
source "$RUNTIME_ENV"
set +a

[[ -n "${SATURN_BASE_URL:-}" && -n "${SATURN_TOKEN:-}" ]] || {
  printf 'Biella Saturn MCP requires SATURN_BASE_URL and SATURN_TOKEN.\n' >&2
  exit 1
}
command -v uvx >/dev/null 2>&1 || {
  printf 'uvx is required for the official Saturn MCP package.\n' >&2
  exit 1
}

exec uvx --from "$SATURN_PLUGIN_SPEC" saturn-mcp
