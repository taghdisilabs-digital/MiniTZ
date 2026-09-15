#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
readonly MINITZ_PRODUCTION_RUNNER="${MINITZ_PRODUCTION_RUNNER:-$SCRIPT_DIR/minitz_production_runner.py}"
readonly RUNTIME_ENV="${MINITZ_AI_RUNTIME_ENV:-/root/attached-storage/minitz-os-sandbox/state/credentials/runtime.env}"
readonly CODEX_BIN="${MINITZ_CODEX_BIN:-/usr/bin/codex}"
export MINITZ_CONTEXT_MODE="${MINITZ_CONTEXT_MODE:-progressive}"
export MINITZ_CONTEXT_MAX_FILES="${MINITZ_CONTEXT_MAX_FILES:-8}"
export MINITZ_CONTEXT_MAX_BYTES="${MINITZ_CONTEXT_MAX_BYTES:-65536}"
export MINITZ_CONTEXT_LOG_TAIL_LINES="${MINITZ_CONTEXT_LOG_TAIL_LINES:-120}"
export MINITZ_CONTEXT_SEARCH_RESULTS="${MINITZ_CONTEXT_SEARCH_RESULTS:-20}"

if [[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$RUNTIME_ENV"
  set +a
fi

readonly SANDBOX_ROOT="${MINITZ_OS_SANDBOX_ROOT:-/root/attached-storage/minitz-os-sandbox}"
readonly SOURCE_ROOT="${MINITZ_REPO_ROOT:-$SANDBOX_ROOT/system/current/opt/minitz/source}"
[[ -d "$SOURCE_ROOT/src/minitz_os" ]] || { printf 'MiniTZ Python source missing: %s
' "$SOURCE_ROOT/src/minitz_os" >&2; exit 1; }
export PYTHONPATH="$SOURCE_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

export HOME="${HOME:-/root}"
export GH_CONFIG_DIR="${GH_CONFIG_DIR:-/root/.config/gh}"
export CODEX_HOME="/root/.codex"
cd /root

if [[ "${1:-}" == "production" ]]; then
  shift
  [[ -x "$MINITZ_PRODUCTION_RUNNER" ]] || { printf 'MiniTZ production runner missing: %s\n' "$MINITZ_PRODUCTION_RUNNER" >&2; exit 1; }
  exec "$MINITZ_PRODUCTION_RUNNER" "$@"
fi

[[ -x "$CODEX_BIN" ]] || { printf 'Codex binary missing: %s\n' "$CODEX_BIN" >&2; exit 1; }
exec "$CODEX_BIN" \
  --dangerously-bypass-approvals-and-sandbox \
  --dangerously-bypass-hook-trust \
  --search \
  -c 'shell_environment_policy.inherit="all"' \
  "$@"
