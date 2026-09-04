#!/usr/bin/env bash
set -Eeuo pipefail

# Codex remains the controller. Ollama is used only as its local OSS worker.
exec codex --oss -m qwen3-coder-next:biella "$@"
