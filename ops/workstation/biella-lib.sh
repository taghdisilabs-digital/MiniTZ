#!/usr/bin/env bash
set -Eeuo pipefail

readonly BIELLA_RUNTIME_ENV="${BIELLA_AI_RUNTIME_ENV:-/root/.config/biella-ai/runtime.env}"
readonly BIELLA_RUNTIME_ROOT="${BIELLA_WORKSTATION_ROOT:-/mnt/biella-extra/biella-runtime}"
readonly BIELLA_OLLAMA_URL="${BIELLA_OLLAMA_URL:-http://127.0.0.1:11434}"
readonly BIELLA_QWEN_MODEL="qwen3-coder-next:biella"

biella_require_root() {
  [[ "$EUID" -eq 0 ]] || { printf 'Biella workstation commands require root.\n' >&2; return 1; }
}

biella_load_runtime_env() {
  [[ -e "$BIELLA_RUNTIME_ENV" ]] || return 0
  [[ -f "$BIELLA_RUNTIME_ENV" && ! -L "$BIELLA_RUNTIME_ENV" ]] || {
    printf 'Runtime env must be a regular file.\n' >&2; return 1;
  }
  [[ "$(stat -c '%u' "$BIELLA_RUNTIME_ENV")" == "0" ]] || {
    printf 'Runtime env must be root-owned.\n' >&2; return 1;
  }
  [[ "$(stat -c '%a' "$BIELLA_RUNTIME_ENV")" == "600" ]] || {
    printf 'Runtime env must have mode 0600.\n' >&2; return 1;
  }
  set -a
  # shellcheck disable=SC1090
  source "$BIELLA_RUNTIME_ENV"
  set +a
}
biella_ensure_runtime_dirs() {
  install -d -o root -g root -m 755 "$BIELLA_RUNTIME_ROOT"
  local name
  for name in cache tmp logs builds models; do
    install -d -o root -g root -m 755 "$BIELLA_RUNTIME_ROOT/$name"
  done
}

biella_ollama_ready() {
  curl -fsS --connect-timeout 2 --max-time 5 "$BIELLA_OLLAMA_URL/api/tags" >/dev/null 2>&1
}

biella_qwen_loaded() {
  curl -fsS --connect-timeout 2 --max-time 5 "$BIELLA_OLLAMA_URL/api/ps" 2>/dev/null |
    python3 -c 'import json,sys; m=sys.argv[1]; d=json.load(sys.stdin); raise SystemExit(0 if any(x.get("name")==m or x.get("model")==m for x in d.get("models",[])) else 1)' "$BIELLA_QWEN_MODEL"
}

biella_status_basic() {
  local ollama=DOWN qwen=NOT_LOADED
  biella_ollama_ready && ollama=READY
  biella_qwen_loaded && qwen=READY
  printf 'Ollama: %s\nQwen:   %s\n' "$ollama" "$qwen"
  printf 'Runtime storage: %s\n' "$BIELLA_RUNTIME_ROOT"
}

biella_exec_or_fail() {
  local command="$1"; shift
  command -v "$command" >/dev/null 2>&1 || { printf 'Missing command: %s\n' "$command" >&2; return 1; }
  exec "$command" "$@"
}
