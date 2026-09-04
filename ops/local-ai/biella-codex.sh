#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
readonly BIELLA_CODEX_FEEDER="${BIELLA_CODEX_FEEDER:-$SCRIPT_DIR/biella_codex_feeder.py}"
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

export CODEX_HOME="/root/.codex"
cd /root

if [[ "${1:-}" == "feed" ]]; then
  shift
  [[ -x "$BIELLA_CODEX_FEEDER" ]] || { printf 'Codex feeder missing: %s\n' "$BIELLA_CODEX_FEEDER" >&2; exit 1; }
  exec "$BIELLA_CODEX_FEEDER" "$@"
fi

[[ -x "$CODEX_BIN" ]] || { printf 'Codex binary missing: %s\n' "$CODEX_BIN" >&2; exit 1; }
exec "$CODEX_BIN" \
  --dangerously-bypass-approvals-and-sandbox \
  --dangerously-bypass-hook-trust \
  --search \
  -c 'shell_environment_policy.inherit="all"' \
  "$@"
