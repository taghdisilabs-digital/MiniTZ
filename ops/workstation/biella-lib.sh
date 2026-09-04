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
readonly BIELLA_QWEN_NUM_GPU=26
readonly BIELLA_QWEN_NUM_CTX=16384
readonly BIELLA_VRAM_LIMIT_BYTES=$((30 * 1024 * 1024 * 1024))

biella_wait_for_ollama() {
  local attempt
  for ((attempt=1; attempt<=60; attempt++)); do
    biella_ollama_ready && return 0
    sleep 1
  done
  return 1
}

biella_start_supervised_ollama() {
  command -v systemctl >/dev/null 2>&1 || return 1
  systemctl list-unit-files biella-ollama.service >/dev/null 2>&1 || return 1
  systemctl start biella-ollama.service
  biella_wait_for_ollama
}

biella_warm_qwen() {
  local payload
  payload="$(python3 - "$BIELLA_QWEN_MODEL" "$BIELLA_QWEN_NUM_GPU" "$BIELLA_QWEN_NUM_CTX" <<'PY'
import json, sys
print(json.dumps({"model":sys.argv[1],"prompt":"Reply with READY only.","stream":False,"keep_alive":-1,"options":{"num_gpu":int(sys.argv[2]),"num_ctx":int(sys.argv[3])}}))
PY
)"
  curl -fsS --connect-timeout 3 --max-time 900 -H 'Content-Type: application/json' --data-binary "$payload" "$BIELLA_OLLAMA_URL/api/generate" >/dev/null
}
biella_verify_qwen_vram() {
  curl -fsS --connect-timeout 3 --max-time 20 "$BIELLA_OLLAMA_URL/api/ps" |
    python3 -c '
import json,sys
model=sys.argv[1]; limit=int(sys.argv[2]); data=json.load(sys.stdin)
items=[x for x in data.get("models",[]) if x.get("name")==model or x.get("model")==model]
if not items: raise SystemExit("Qwen is not loaded")
vram=items[0].get("size_vram")
if not isinstance(vram,int) or vram<=0 or vram>=limit: raise SystemExit("Qwen VRAM contract failed")
print(vram)
' "$BIELLA_QWEN_MODEL" "$BIELLA_VRAM_LIMIT_BYTES"
}

biella_verify_v1_responses() {
  local base payload
  base="${BIELLA_OLLAMA_URL%/api}"
  base="${base%/}"
  payload="$(python3 - "$BIELLA_QWEN_MODEL" <<'PY'
import json,sys
print(json.dumps({"model":sys.argv[1],"input":"Reply with READY only."}))
PY
)"
  curl -fsS --connect-timeout 3 --max-time 300 -H 'Content-Type: application/json' \
    --data-binary "$payload" "$base/v1/responses" |
    python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("status") in {"completed","in_progress"} else 1)'
}

biella_up_local() {
  biella_ollama_ready || biella_start_supervised_ollama || {
    printf 'Biella Ollama service is unavailable.\n' >&2; return 1;
  }
  biella_warm_qwen
  biella_verify_qwen_vram >/dev/null
  biella_verify_v1_responses
}
biella_kill_matching_signature() {
  local signature="$1" pid cmdline
  while read -r pid; do
    [[ -r "/proc/$pid/cmdline" ]] || continue
    cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
    [[ "$cmdline" == *"$signature"* ]] || continue
    kill "$pid" 2>/dev/null || true
  done < <(pgrep -f -- "$signature" 2>/dev/null || true)
}

biella_cleanup_legacy() {
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t llm-router 2>/dev/null; then
    tmux kill-session -t llm-router
  fi
  biella_kill_matching_signature 'python3 -m http.server 61374 --bind 0.0.0.0 --directory /mnt/biella-production/BiellaProduction'
  biella_kill_matching_signature 'python3 -m http.server 81374 --bind 0.0.0.0 --directory /mnt/biella-production/BiellaProduction'
  biella_kill_matching_signature 'cloudflared tunnel --no-autoupdate --url http://127.0.0.1:61374'
}

biella_gpu_status() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv,noheader 2>/dev/null | head -n 1
  else
    printf 'unavailable\n'
  fi
}

biella_disk_status() {
  df -h "$BIELLA_RUNTIME_ROOT" 2>/dev/null | awk 'NR==2 {print $2" total, "$3" used, "$4" free"}'
}
