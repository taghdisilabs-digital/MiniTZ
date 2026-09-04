#!/usr/bin/env bash
set -Eeuo pipefail

readonly RUNTIME_ENV="${BIELLA_AI_RUNTIME_ENV:-/root/.config/biella-ai/runtime.env}"
readonly CODEX_BIN="${BIELLA_CODEX_BIN:-/usr/bin/codex}"

if [[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$RUNTIME_ENV"
  set +a
fi

# Codex remains the controller; Ollama is the local Qwen worker.
# This worker is intentionally unrestricted at the Codex approval/sandbox layer.
exec "$CODEX_BIN" \
  --oss \
  --local-provider ollama \
  -m qwen3-coder-next:biella \
  --dangerously-bypass-approvals-and-sandbox \
  --dangerously-bypass-hook-trust \
  --search \
  "$@"
