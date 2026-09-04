#!/usr/bin/env bash
set -Eeuo pipefail

readonly RUNTIME_ENV="${BIELLA_AI_RUNTIME_ENV:-/root/.config/biella-ai/runtime.env}"
if [[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$RUNTIME_ENV"
  set +a
fi

# Codex remains the controller. Ollama is used only as its local OSS worker.
exec codex --oss -m qwen3-coder-next:biella "$@"
