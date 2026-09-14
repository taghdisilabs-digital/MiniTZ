#!/usr/bin/env bash
set -Eeuo pipefail

readonly MINITZ_RUNTIME_ENV="${MINITZ_AI_RUNTIME_ENV:-/root/attached-storage/minitz-os-sandbox/state/credentials/runtime.env}"
readonly MINITZ_CLOUDFLARE_CREDENTIAL_ENV="${MINITZ_CLOUDFLARE_CREDENTIAL_ENV:-/root/attached-storage/minitz-os-sandbox/state/credentials/cloudflare.env}"
readonly MINITZ_RUNTIME_ROOT="${MINITZ_WORKSTATION_ROOT:-/root/attached-storage/minitz-os-sandbox/state/workstation}"
readonly MINITZ_OLLAMA_URL="${MINITZ_OLLAMA_URL:-http://127.0.0.1:11434}"
readonly MINITZ_QWEN_MODEL="${MINITZ_QWEN_MODEL:-qwen3-coder-next:minitz}"
readonly MINITZ_QWEN_NUM_GPU="${MINITZ_QWEN_NUM_GPU:-38}"
readonly MINITZ_QWEN_NUM_CTX="${MINITZ_QWEN_NUM_CTX:-16384}"

minitz_require_root() { [[ "$EUID" -eq 0 ]] || { printf 'MiniTZ workstation commands require root.\n' >&2; return 1; }; }
minitz_load_protected_env_file() {
  local path="$1" label="$2"
  [[ -e "$path" ]] || return 0
  [[ -f "$path" && ! -L "$path" ]] || { printf '%s must be a regular file.\n' "$label" >&2; return 1; }
  [[ "$(stat -c '%u' "$path")" == 0 ]] || { printf '%s must be root-owned.\n' "$label" >&2; return 1; }
  [[ "$(stat -c '%a' "$path")" == 600 ]] || { printf '%s must have mode 0600.\n' "$label" >&2; return 1; }
  set -a; source "$path"; set +a
}
minitz_load_runtime_env() {
  minitz_load_protected_env_file "$MINITZ_RUNTIME_ENV" 'MiniTZ runtime env'
  minitz_load_protected_env_file "$MINITZ_CLOUDFLARE_CREDENTIAL_ENV" 'MiniTZ Cloudflare credential env'
}
minitz_ensure_runtime_dirs() { install -d -o root -g root -m 755 "$MINITZ_RUNTIME_ROOT" "$MINITZ_RUNTIME_ROOT/cache" "$MINITZ_RUNTIME_ROOT/tmp" "$MINITZ_RUNTIME_ROOT/logs"; }
minitz_ollama_ready() { curl -fsS --connect-timeout 2 --max-time 5 "$MINITZ_OLLAMA_URL/api/tags" >/dev/null 2>&1; }
minitz_qwen_loaded() {
  curl -fsS --connect-timeout 2 --max-time 5 "$MINITZ_OLLAMA_URL/api/ps" 2>/dev/null |
    python3 -c 'import json,sys;m=sys.argv[1];d=json.load(sys.stdin);raise SystemExit(0 if any(x.get("name")==m or x.get("model")==m for x in d.get("models",[])) else 1)' "$MINITZ_QWEN_MODEL"
}
minitz_warm_qwen() {
  minitz_ollama_ready || { printf 'Existing Ollama resource is unavailable.\n' >&2; return 1; }
  local payload
  payload="$(python3 - "$MINITZ_QWEN_MODEL" "$MINITZ_QWEN_NUM_GPU" "$MINITZ_QWEN_NUM_CTX" <<'PY'
import json,sys
print(json.dumps({'model':sys.argv[1],'prompt':'Reply with READY only.','stream':False,'keep_alive':-1,'options':{'num_gpu':int(sys.argv[2]),'num_ctx':int(sys.argv[3])}}))
PY
)"
  curl -fsS --connect-timeout 3 --max-time 900 -H 'Content-Type: application/json' --data-binary "$payload" "$MINITZ_OLLAMA_URL/api/generate" >/dev/null
}
minitz_qwen_vram() {
  curl -fsS --connect-timeout 3 --max-time 20 "$MINITZ_OLLAMA_URL/api/ps" |
    python3 -c 'import json,sys;m=sys.argv[1];d=json.load(sys.stdin);x=next((r for r in d.get("models",[]) if r.get("name")==m or r.get("model")==m),None);assert x and isinstance(x.get("size_vram"),int);print(x["size_vram"])' "$MINITZ_QWEN_MODEL"
}
minitz_verify_v1_responses() {
  local base="${MINITZ_OLLAMA_URL%/api}" payload
  payload="$(python3 - "$MINITZ_QWEN_MODEL" <<'PY'
import json,sys
print(json.dumps({'model':sys.argv[1],'input':'Reply with READY only.'}))
PY
)"
  curl -fsS --connect-timeout 3 --max-time 300 -H 'Content-Type: application/json' --data-binary "$payload" "${base%/}/v1/responses" |
    python3 -c 'import json,sys;d=json.load(sys.stdin);raise SystemExit(0 if d.get("status") in {"completed","in_progress"} else 1)'
}
minitz_status_basic() {
  local ollama=DOWN qwen=NOT_LOADED
  minitz_ollama_ready && ollama=READY
  minitz_qwen_loaded && qwen=READY
  printf 'Ollama: %s\nQwen:   %s\nRuntime storage: %s\n' "$ollama" "$qwen" "$MINITZ_RUNTIME_ROOT"
}
minitz_exec_or_fail() { local command="$1"; shift; command -v "$command" >/dev/null 2>&1 || { printf 'Missing command: %s\n' "$command" >&2; return 1; }; exec "$command" "$@"; }
minitz_gpu_status() { command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || printf 'unavailable\n'; }
minitz_disk_status() { df -h "$MINITZ_RUNTIME_ROOT" 2>/dev/null | awk 'NR==2 {print $2" total, "$3" used, "$4" free"}'; }
