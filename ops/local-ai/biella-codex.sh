#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
readonly BIELLA_PRODUCTION_RUNNER="${BIELLA_PRODUCTION_RUNNER:-$SCRIPT_DIR/biella_production_runner.py}"
readonly RUNTIME_ENV="${BIELLA_AI_RUNTIME_ENV:-/root/.config/biella-ai/runtime.env}"
readonly CODEX_BIN="${BIELLA_CODEX_BIN:-/usr/bin/codex}"
export BIELLA_CONTEXT_MODE="${BIELLA_CONTEXT_MODE:-progressive}"
export BIELLA_CONTEXT_MAX_FILES="${BIELLA_CONTEXT_MAX_FILES:-8}"
export BIELLA_CONTEXT_MAX_BYTES="${BIELLA_CONTEXT_MAX_BYTES:-65536}"
export BIELLA_CONTEXT_LOG_TAIL_LINES="${BIELLA_CONTEXT_LOG_TAIL_LINES:-120}"
export BIELLA_CONTEXT_SEARCH_RESULTS="${BIELLA_CONTEXT_SEARCH_RESULTS:-20}"

if [[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$RUNTIME_ENV"
  set +a
fi

export HOME="${HOME:-/root}"
export GH_CONFIG_DIR="${GH_CONFIG_DIR:-/root/.config/gh}"
export CODEX_HOME="/root/.codex"
cd /root

if [[ "${1:-}" == "production" ]]; then
  shift
  [[ -x "$BIELLA_PRODUCTION_RUNNER" ]] || { printf 'Biella production runner missing: %s\n' "$BIELLA_PRODUCTION_RUNNER" >&2; exit 1; }
  exec "$BIELLA_PRODUCTION_RUNNER" "$@"
fi

[[ -x "$CODEX_BIN" ]] || { printf 'Codex binary missing: %s\n' "$CODEX_BIN" >&2; exit 1; }
exec "$CODEX_BIN" \
  --dangerously-bypass-approvals-and-sandbox \
  --dangerously-bypass-hook-trust \
  --search \
  -c 'shell_environment_policy.inherit="all"' \
  "$@"
