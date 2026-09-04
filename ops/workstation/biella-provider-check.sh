#!/usr/bin/env bash
set -Eeuo pipefail

readonly SELF="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd -P)"
# shellcheck source=biella-lib.sh
source "$SCRIPT_DIR/biella-lib.sh"
biella_load_runtime_env
biella_ensure_runtime_dirs

check_bearer() {
  local name="$1" url="$2" token="$3" code tmp
  tmp="$(mktemp "$BIELLA_RUNTIME_ROOT/tmp/provider.XXXXXX")"
  code="$(curl -s -o "$tmp" -w '%{http_code}' -H "Authorization: Bearer $token" "$url" || true)"
  rm -f -- "$tmp"
  if [[ "$code" == 2* ]]; then
    printf '%-12s CONNECTED HTTP=%s\n' "$name" "$code"
  else
    printf '%-12s DEGRADED  HTTP=%s\n' "$name" "${code:-000}"
  fi
}

check_api_key_header() {
  local name="$1" url="$2" token="$3" code tmp
  tmp="$(mktemp "$BIELLA_RUNTIME_ROOT/tmp/provider.XXXXXX")"
  code="$(curl -s -o "$tmp" -w '%{http_code}' -H "x-goog-api-key: $token" "$url" || true)"
  rm -f -- "$tmp"
  [[ "$code" == 2* ]] && printf '%-12s CONNECTED HTTP=%s\n' "$name" "$code" || printf '%-12s DEGRADED  HTTP=%s\n' "$name" "${code:-000}"
}
if [[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" && -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  check_bearer Cloudflare "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/models/search" "$CLOUDFLARE_API_TOKEN"
else
  printf '%-12s NOT_CONFIGURED\n' Cloudflare
fi

[[ -n "${GROQ_API_KEY:-}" ]] && check_bearer Groq 'https://api.groq.com/openai/v1/models' "$GROQ_API_KEY" || printf '%-12s NOT_CONFIGURED\n' Groq
[[ -n "${CEREBRAS_API_KEY:-}" ]] && check_bearer Cerebras 'https://api.cerebras.ai/v1/models' "$CEREBRAS_API_KEY" || printf '%-12s NOT_CONFIGURED\n' Cerebras
[[ -n "${OPENROUTER_API_KEY:-}" ]] && check_bearer OpenRouter 'https://openrouter.ai/api/v1/models' "$OPENROUTER_API_KEY" || printf '%-12s NOT_CONFIGURED\n' OpenRouter
[[ -n "${MISTRAL_API_KEY:-}" ]] && check_bearer Mistral 'https://api.mistral.ai/v1/models' "$MISTRAL_API_KEY" || printf '%-12s NOT_CONFIGURED\n' Mistral
[[ -n "${TAVILY_API_KEY:-}" ]] && check_bearer Tavily 'https://api.tavily.com/usage' "$TAVILY_API_KEY" || printf '%-12s NOT_CONFIGURED\n' Tavily

if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  check_api_key_header Gemini 'https://generativelanguage.googleapis.com/v1beta/models' "$GEMINI_API_KEY"
else
  printf '%-12s NOT_CONFIGURED\n' Gemini
fi

if command -v modal >/dev/null 2>&1 && modal token info >/dev/null 2>&1; then
  printf '%-12s CONNECTED\n' Modal
else
  printf '%-12s DEGRADED\n' Modal
fi

if command -v codex >/dev/null 2>&1 && codex mcp list 2>/dev/null | grep -qi '^saturn .*enabled'; then
  printf '%-12s CONNECTED\n' Saturn
else
  printf '%-12s DEGRADED\n' Saturn
fi
