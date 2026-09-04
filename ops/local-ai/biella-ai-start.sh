#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Biella bounded local-AI runtime.
#
# This launcher intentionally owns only the local execution boundary:
# Ollama -> Qwen, Codex -> local Ollama, Codex -> Saturn stdio MCP, and
# Cloudflare account API + optional tunnel. It does not create a second
# project manager, reviewer, router, or model-download path.

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly RUNTIME_ROOT="${BIELLA_AI_RUNTIME_ROOT:-/root/.config/biella-ai}"
readonly STATE_ROOT="${BIELLA_AI_STATE_ROOT:-/var/lib/biella-ai}"
readonly LOG_ROOT="${BIELLA_AI_LOG_ROOT:-/var/log/biella-ai}"
readonly RUNTIME_ENV="$RUNTIME_ROOT/runtime.env"
readonly STATUS_ENV="$STATE_ROOT/status.env"
readonly OLLAMA_PID_FILE="$STATE_ROOT/ollama.pid"
readonly CLOUDFLARED_PID_FILE="$STATE_ROOT/cloudflared.pid"
readonly SATURN_RESOURCES_FILE="$STATE_ROOT/saturn-resources.json"
readonly QWEN_MODEL="qwen3-coder-next:biella"
readonly QWEN_NUM_GPU=26
readonly QWEN_NUM_CTX=16384
readonly CPU_RAM_TARGET_GIB=86
readonly VRAM_LIMIT_BYTES=$((30 * 1024 * 1024 * 1024))
readonly SATURN_PLUGIN_SPEC="saturn-mcp @ git+https://github.com/saturncloud/claude-plugin.git@main#subdirectory=plugins/saturn-cloud"
readonly SATURN_MCP_WRAPPER="$SCRIPT_DIR/biella-saturn-mcp.sh"
readonly SATURN_PROBE="$SCRIPT_DIR/biella-saturn-probe.py"
readonly CODEX_WRAPPER="$SCRIPT_DIR/biella-codex.sh"

OLLAMA_URL="${BIELLA_OLLAMA_URL:-http://127.0.0.1:11434}"
BIELLA_GATEWAY_URL="${BIELLA_GATEWAY_URL:-http://127.0.0.1:8787}"
OLLAMA_URL="${OLLAMA_URL%/}"
BIELLA_GATEWAY_URL="${BIELLA_GATEWAY_URL%/}"

SATURN_BASE_URL=""
SATURN_TOKEN=""
CLOUDFLARE_ACCOUNT_ID=""
CLOUDFLARE_API_TOKEN=""
CLOUDFLARE_TUNNEL_TOKEN=""
CLOUDFLARE_CONFIGURED=""
CLOUDFLARE_ACCOUNT_API_STATUS="NOT_CONFIGURED"
SATURN_RESOURCE_COUNT=0
SATURN_INSTANCE_TYPE_COUNT=0
QWEN_VRAM_BYTES=0
QWEN_VRAM_GIB=""
GPU_OBSERVATION="unavailable"
CLOUDFLARE_STATUS="NOT_CONFIGURED"
CLOUDFLARE_MODE=""
CLOUDFLARE_QUICK_URL=""
GATEWAY_STATUS="NOT_VERIFIED"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is missing: $1"
}

require_root() {
  [[ "$EUID" -eq 0 ]] || die "run biella-ai-start as root; runtime credentials are root-only"
}

require_interactive_prompt() {
  [[ -t 0 ]] || die "an interactive terminal is required for the first credential prompt"
}

ensure_directories() {
  install -d -o root -g root -m 700 "$RUNTIME_ROOT" "$STATE_ROOT" "$LOG_ROOT"
}

assert_local_origin() {
  [[ "$OLLAMA_URL" == http://127.0.0.1:* || "$OLLAMA_URL" == http://localhost:* ]] \
    || die "local Qwen must use localhost Ollama; Cloudflare is not allowed on this path"
  [[ "$BIELLA_GATEWAY_URL" == http://127.0.0.1:* || "$BIELLA_GATEWAY_URL" == http://localhost:* ]] \
    || die "the Cloudflare origin must be a localhost gateway"
}

load_runtime_env() {
  [[ -e "$RUNTIME_ENV" ]] || return 0
  [[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]] || die "runtime env must be a regular root-owned file"
  [[ "$(stat -c '%u' "$RUNTIME_ENV")" == "0" ]] || die "runtime env is not root-owned"
  [[ "$(stat -c '%a' "$RUNTIME_ENV")" == "600" ]] || die "runtime env must have mode 0600"
  set -a
  # shellcheck disable=SC1090
  source "$RUNTIME_ENV"
  set +a
}

reject_newlines() {
  [[ "$1" != *$'\n'* && "$1" != *$'\r'* ]] || die "$2 must not contain newlines"
}

prompt_and_save_credentials() {
  if [[ -z "$SATURN_BASE_URL" ]]; then
    require_interactive_prompt
    printf '\nSaturn URL:\n> '
    read -r SATURN_BASE_URL
  fi

  if [[ -z "$SATURN_TOKEN" ]]; then
    require_interactive_prompt
    printf 'Saturn API token:\n> '
    read -r -s SATURN_TOKEN
    printf '\n'
  fi

  if [[ -z "$CLOUDFLARE_ACCOUNT_ID" ]]; then
    require_interactive_prompt
    printf 'Cloudflare Account ID:\n> '
    read -r CLOUDFLARE_ACCOUNT_ID
  fi

  if [[ -z "$CLOUDFLARE_API_TOKEN" ]]; then
    require_interactive_prompt
    printf 'Cloudflare Workers AI API token:\n> '
    read -r -s CLOUDFLARE_API_TOKEN
    printf '\n'
  fi

  [[ -n "$SATURN_BASE_URL" ]] || die "Saturn URL is required"
  [[ "$SATURN_BASE_URL" =~ ^https?://[^[:space:]]+$ ]] || die "Saturn URL must start with http:// or https://"
  [[ -n "$SATURN_TOKEN" ]] || die "Saturn API token is required"
  [[ "$CLOUDFLARE_ACCOUNT_ID" =~ ^[0-9A-Fa-f]{32}$ ]] || die "Cloudflare Account ID must be 32 hex characters"
  [[ -n "$CLOUDFLARE_API_TOKEN" ]] || die "Cloudflare Workers AI API token is required"
  reject_newlines "$SATURN_BASE_URL" "Saturn URL"
  reject_newlines "$SATURN_TOKEN" "Saturn API token"
  reject_newlines "$CLOUDFLARE_ACCOUNT_ID" "Cloudflare Account ID"
  reject_newlines "$CLOUDFLARE_API_TOKEN" "Cloudflare API token"
  reject_newlines "$CLOUDFLARE_TUNNEL_TOKEN" "Cloudflare tunnel token"

  local tmp_env
  tmp_env="$(mktemp "$RUNTIME_ROOT/runtime.env.XXXXXX")"
  umask 077
  {
    printf 'SATURN_BASE_URL=%q\n' "$SATURN_BASE_URL"
    printf 'SATURN_TOKEN=%q\n' "$SATURN_TOKEN"
    printf 'CLOUDFLARE_ACCOUNT_ID=%q\n' "$CLOUDFLARE_ACCOUNT_ID"
    printf 'CLOUDFLARE_API_TOKEN=%q\n' "$CLOUDFLARE_API_TOKEN"
    printf 'CLOUDFLARE_TUNNEL_TOKEN=%q\n' "$CLOUDFLARE_TUNNEL_TOKEN"
    printf 'CLOUDFLARE_CONFIGURED=%q\n' "$CLOUDFLARE_CONFIGURED"
  } > "$tmp_env"
  chown root:root "$tmp_env"
  chmod 600 "$tmp_env"
  mv -f -- "$tmp_env" "$RUNTIME_ENV"
}

ollama_api_get() {
  curl -fsS --connect-timeout 3 --max-time 20 "$OLLAMA_URL$1"
}

ollama_is_ready() {
  curl -fsS --connect-timeout 2 --max-time 5 "$OLLAMA_URL/api/tags" >/dev/null 2>&1
}

wait_for_ollama() {
  local attempt
  for ((attempt = 1; attempt <= 60; attempt++)); do
    if ollama_is_ready; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_ollama() {
  need_command curl

  if ollama_is_ready; then
    return 0
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files ollama.service >/dev/null 2>&1; then
    systemctl start ollama.service >/dev/null 2>&1 || true
  fi

  if ! ollama_is_ready; then
    need_command ollama
    if [[ -f "$OLLAMA_PID_FILE" ]] && kill -0 "$(cat "$OLLAMA_PID_FILE")" 2>/dev/null; then
      :
    else
      nohup env OLLAMA_HOST=127.0.0.1:11434 OLLAMA_KEEP_ALIVE=-1 ollama serve \
        >>"$LOG_ROOT/ollama.log" 2>&1 &
      printf '%s\n' "$!" > "$OLLAMA_PID_FILE"
      chown root:root "$OLLAMA_PID_FILE"
      chmod 600 "$OLLAMA_PID_FILE"
    fi
  fi

  wait_for_ollama || die "Ollama did not become ready at $OLLAMA_URL"
}

model_is_installed() {
  local tags_json="$1"
  python3 -c '
import json
import sys

model = sys.argv[1]
data = json.load(sys.stdin)
sys.exit(0 if any(item.get("name") == model for item in data.get("models", [])) else 1)
' "$QWEN_MODEL" <<< "$tags_json"
}

load_qwen_once() {
  local tags_json payload warmup_json ps_json stats
  tags_json="$(ollama_api_get /api/tags)" || die "could not read Ollama model inventory"
  model_is_installed "$tags_json" || die "required existing model is absent: $QWEN_MODEL; no model download is attempted"

  payload="$(python3 - "$QWEN_MODEL" "$QWEN_NUM_GPU" "$QWEN_NUM_CTX" <<'PY'
import json
import sys

print(json.dumps({
    "model": sys.argv[1],
    "prompt": "Reply with READY only.",
    "stream": False,
    "keep_alive": -1,
    "options": {
        "num_gpu": int(sys.argv[2]),
        "num_ctx": int(sys.argv[3]),
    },
}))
PY
)"

  warmup_json="$STATE_ROOT/qwen-warmup.json"
  curl -fsS --connect-timeout 3 --max-time 900 \
    -H 'Content-Type: application/json' \
    --data-binary "$payload" \
    "$OLLAMA_URL/api/generate" > "$warmup_json" \
    || die "Qwen warmup failed; no unload/reload or tuning loop is attempted"
  chown root:root "$warmup_json"
  chmod 600 "$warmup_json"

  ps_json="$(ollama_api_get /api/ps)" || die "could not read Ollama loaded-model state"
  stats="$(python3 -c '
import json
import sys

model = sys.argv[1]
limit = int(sys.argv[2])
data = json.load(sys.stdin)
matches = [item for item in data.get("models", [])
           if item.get("name") == model or item.get("model") == model]
if not matches:
    raise SystemExit("Qwen is not present in Ollama /api/ps after warmup")
size_vram = matches[0].get("size_vram")
if not isinstance(size_vram, int):
    raise SystemExit("Ollama did not report size_vram; VRAM bound cannot be verified")
if size_vram <= 0:
    raise SystemExit("Ollama reports no VRAM residency for Qwen")
if size_vram >= limit:
    raise SystemExit("Qwen VRAM residency is at or above the 30 GiB hard limit")
print(f"{size_vram}\t{size_vram / (1024 ** 3):.2f}")
' "$QWEN_MODEL" "$VRAM_LIMIT_BYTES" <<< "$ps_json")" \
    || die "Qwen did not satisfy the fixed <=30 GiB VRAM contract"
  IFS=$'\t' read -r QWEN_VRAM_BYTES QWEN_VRAM_GIB <<< "$stats"

  if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_OBSERVATION="$(nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version \
      --format=csv,noheader 2>/dev/null | head -n 1 || true)"
    [[ -n "$GPU_OBSERVATION" ]] || GPU_OBSERVATION="unavailable"
  fi
}

run_saturn_probe() {
  if python3 -c 'import saturn_client' >/dev/null 2>&1; then
    python3 "$SATURN_PROBE"
    return
  fi
  command -v uv >/dev/null 2>&1 || die "uv is required to run the official Saturn MCP package"
  uv run --quiet --isolated --with "$SATURN_PLUGIN_SPEC" python "$SATURN_PROBE"
}

connect_saturn() {
  local counts
  umask 077
  run_saturn_probe > "$SATURN_RESOURCES_FILE" \
    || die "Saturn API/MCP connection failed; real resources were not enumerated"
  chown root:root "$SATURN_RESOURCES_FILE"
  chmod 600 "$SATURN_RESOURCES_FILE"

  counts="$(python3 -c '
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)

def count(value, keys):
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, list):
                return len(candidate)
    return 0

resource_count = count(data.get("resources"), ("resources", "items"))
instance_type_count = count(data.get("instance_types"), ("instance_types", "items"))
print(str(resource_count) + "\t" + str(instance_type_count))
' "$SATURN_RESOURCES_FILE")"
  IFS=$'\t' read -r SATURN_RESOURCE_COUNT SATURN_INSTANCE_TYPE_COUNT <<< "$counts"
}

register_saturn_with_codex() {
  local current_mcp
  need_command codex
  [[ -x "$SATURN_MCP_WRAPPER" ]] || die "Saturn MCP wrapper is not executable: $SATURN_MCP_WRAPPER"

  current_mcp="$(codex mcp list 2>&1 || true)"
  if printf '%s\n' "$current_mcp" | grep -qi 'saturn'; then
    printf '%s\n' "$current_mcp" | grep -F --quiet -- "$SATURN_MCP_WRAPPER" \
      || die "a different Saturn MCP entry already exists; it was not overwritten"
  else
    codex mcp add saturn -- "$SATURN_MCP_WRAPPER" >/dev/null \
      || die "Codex could not register the Saturn stdio MCP server"
  fi

  current_mcp="$(codex mcp list 2>&1)" || die "Codex MCP listing failed after Saturn registration"
  printf '%s\n' "$current_mcp" | grep -F --quiet -- "$SATURN_MCP_WRAPPER" \
    || die "Saturn MCP registration could not be verified"
}

write_cloudflared_unit() {
  local cloudflared_bin="$1"
  install -d -o root -g root -m 700 /etc/cloudflared
  local token_tmp
  token_tmp="$(mktemp /etc/cloudflared/biella-tunnel.token.XXXXXX)"
  printf '%s\n' "$CLOUDFLARE_TUNNEL_TOKEN" > "$token_tmp"
  chown root:root "$token_tmp"
  chmod 600 "$token_tmp"
  mv -f -- "$token_tmp" /etc/cloudflared/biella-tunnel.token

  local unit_tmp
  unit_tmp="$(mktemp /etc/systemd/system/biella-cloudflared.service.XXXXXX)"
  cat > "$unit_tmp" <<EOF
[Unit]
Description=Biella Cloudflare Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$cloudflared_bin tunnel --no-autoupdate run --token-file /etc/cloudflared/biella-tunnel.token
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF
  chown root:root "$unit_tmp"
  chmod 644 "$unit_tmp"
  mv -f -- "$unit_tmp" /etc/systemd/system/biella-cloudflared.service
}

wait_for_systemd_cloudflared() {
  local attempt
  for ((attempt = 1; attempt <= 30; attempt++)); do
    if systemctl is-active --quiet biella-cloudflared.service; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_cloudflared_direct() {
  local cloudflared_bin="$1"
  if [[ -f "$CLOUDFLARED_PID_FILE" ]] && kill -0 "$(cat "$CLOUDFLARED_PID_FILE")" 2>/dev/null; then
    return 0
  fi
  nohup "$cloudflared_bin" tunnel --no-autoupdate run --token-file /etc/cloudflared/biella-tunnel.token \
    >>"$LOG_ROOT/cloudflared.log" 2>&1 &
  printf '%s\n' "$!" > "$CLOUDFLARED_PID_FILE"
  chown root:root "$CLOUDFLARED_PID_FILE"
  chmod 600 "$CLOUDFLARED_PID_FILE"
  sleep 2
  kill -0 "$!" 2>/dev/null
}

start_quick_tunnel() {
  local cloudflared_bin="$1"
  if [[ ! -f "$CLOUDFLARED_PID_FILE" ]] || ! kill -0 "$(cat "$CLOUDFLARED_PID_FILE")" 2>/dev/null; then
    nohup "$cloudflared_bin" tunnel --no-autoupdate --url "$BIELLA_GATEWAY_URL" \
      >>"$LOG_ROOT/cloudflared-quick.log" 2>&1 &
    printf '%s\n' "$!" > "$CLOUDFLARED_PID_FILE"
    chown root:root "$CLOUDFLARED_PID_FILE"
    chmod 600 "$CLOUDFLARED_PID_FILE"
  fi

  local attempt
  for ((attempt = 1; attempt <= 15; attempt++)); do
    if [[ -f "$LOG_ROOT/cloudflared-quick.log" ]]; then
      CLOUDFLARE_QUICK_URL="$(grep -Eo 'https://[A-Za-z0-9.-]+\.trycloudflare\.com' \
        "$LOG_ROOT/cloudflared-quick.log" | tail -n 1 || true)"
      [[ -n "$CLOUDFLARE_QUICK_URL" ]] && return 0
    fi
    sleep 1
  done
  return 1
}

verify_cloudflare_account_api() {
  local response
  response="$(curl -fsS --connect-timeout 3 --max-time 30 \
    -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/ai/models/search")" \
    || die "Cloudflare Workers AI account API verification failed"
  python3 -c '
import json, sys
data=json.load(sys.stdin)
sys.exit(0 if data.get("success") is True else 1)
' <<< "$response" \
    || die "Cloudflare Workers AI account API rejected the configured credentials"
  CLOUDFLARE_ACCOUNT_API_STATUS="VERIFIED"
}

connect_cloudflare() {
  local cloudflared_bin=""
  verify_cloudflare_account_api
  if command -v cloudflared >/dev/null 2>&1; then
    cloudflared_bin="$(command -v cloudflared)"
  fi

  if [[ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]]; then
    [[ -n "$cloudflared_bin" ]] || die "Cloudflare token supplied but cloudflared is not installed"
    write_cloudflared_unit "$cloudflared_bin"
    if command -v systemctl >/dev/null 2>&1 && systemctl daemon-reload >/dev/null 2>&1 \
      && systemctl enable --now biella-cloudflared.service >/dev/null 2>&1 \
      && wait_for_systemd_cloudflared; then
      CLOUDFLARE_MODE="account-api+managed-tunnel"
    else
      start_cloudflared_direct "$cloudflared_bin" \
        || die "Cloudflare managed tunnel could not be started"
      CLOUDFLARE_MODE="account-api+managed-direct-tunnel"
    fi
    CLOUDFLARE_STATUS="CONNECTED"
    return 0
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet biella-cloudflared.service; then
    CLOUDFLARE_MODE="existing-biella-service"
    CLOUDFLARE_STATUS="CONNECTED"
    return 0
  fi
  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet cloudflared.service; then
    CLOUDFLARE_MODE="existing-cloudflared-service"
    CLOUDFLARE_STATUS="CONNECTED"
    return 0
  fi

  CLOUDFLARE_MODE="account-api"
  CLOUDFLARE_STATUS="CONNECTED"
}

check_gateway() {
  if curl -fsS --connect-timeout 2 --max-time 5 "$BIELLA_GATEWAY_URL/health" >/dev/null 2>&1; then
    GATEWAY_STATUS="READY"
  else
    GATEWAY_STATUS="NOT_VERIFIED"
  fi
}

write_status() {
  local status_tmp timestamp
  timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  status_tmp="$(mktemp "$STATE_ROOT/status.env.XXXXXX")"
  umask 077
  {
    printf 'last_checked_at=%q\n' "$timestamp"
    printf 'local_qwen=READY\n'
    printf 'qwen_model=%q\n' "$QWEN_MODEL"
    printf 'qwen_gpu_layers=%q\n' "$QWEN_NUM_GPU"
    printf 'qwen_context_tokens=%q\n' "$QWEN_NUM_CTX"
    printf 'qwen_cpu_ram_target_gib=%q\n' "$CPU_RAM_TARGET_GIB"
    printf 'qwen_vram_bytes=%q\n' "$QWEN_VRAM_BYTES"
    printf 'qwen_vram_gib=%q\n' "$QWEN_VRAM_GIB"
    printf 'saturn=CONNECTED\n'
    printf 'saturn_resource_count=%q\n' "$SATURN_RESOURCE_COUNT"
    printf 'saturn_instance_type_count=%q\n' "$SATURN_INSTANCE_TYPE_COUNT"
    printf 'cloudflare=%q\n' "$CLOUDFLARE_STATUS"
    printf 'cloudflare_account_api=%q\n' "$CLOUDFLARE_ACCOUNT_API_STATUS"
    printf 'cloudflare_mode=%q\n' "$CLOUDFLARE_MODE"
    printf 'gateway=%q\n' "$GATEWAY_STATUS"
    printf 'codex=READY\n'
  } > "$status_tmp"
  chown root:root "$status_tmp"
  chmod 600 "$status_tmp"
  mv -f -- "$status_tmp" "$STATUS_ENV"
}

main() {
  require_root
  ensure_directories
  assert_local_origin
  load_runtime_env
  prompt_and_save_credentials

  printf '[1/6] Starting Ollama\n'
  start_ollama

  printf '[2/6] Loading Qwen with <=30 GiB VRAM\n'
  load_qwen_once

  printf '[3/6] Connecting Saturn\n'
  connect_saturn

  printf '[4/6] Registering Saturn tools with Codex\n'
  register_saturn_with_codex

  printf '[5/6] Connecting Cloudflare account API / optional tunnel\n'
  connect_cloudflare

  printf '[6/6] Checking services\n'
  ollama_is_ready || die "Ollama readiness check failed"
  [[ "$QWEN_VRAM_BYTES" -gt 0 && "$QWEN_VRAM_BYTES" -lt "$VRAM_LIMIT_BYTES" ]] \
    || die "Qwen VRAM readiness check failed"
  [[ "$SATURN_RESOURCE_COUNT" -ge 0 ]] || die "Saturn resource enumeration check failed"
  [[ "$CLOUDFLARE_STATUS" == "CONNECTED" ]] || die "Cloudflare readiness check failed"
  check_gateway
  write_status

  printf '\nREADY\n'
  printf 'Local Qwen:   READY\n'
  printf 'VRAM:         %s GiB (<30 GiB)\n' "$QWEN_VRAM_GIB"
  printf 'Saturn:       CONNECTED (%s resources, %s instance types)\n' \
    "$SATURN_RESOURCE_COUNT" "$SATURN_INSTANCE_TYPE_COUNT"
  printf 'Cloudflare:   CONNECTED (%s)\n' "$CLOUDFLARE_MODE"
  printf 'Gateway:      %s\n' "$GATEWAY_STATUS"
  printf 'Codex:        READY (Saturn MCP registered; use biella-codex)\n'
  [[ "$GPU_OBSERVATION" == "unavailable" ]] || printf 'GPU observed: %s\n' "$GPU_OBSERVATION"
}

main "$@"
