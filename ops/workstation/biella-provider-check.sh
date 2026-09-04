#!/usr/bin/env bash
set -Eeuo pipefail

readonly SELF="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd -P)"
# shellcheck source=biella-lib.sh
source "$SCRIPT_DIR/biella-lib.sh"
biella_load_runtime_env
biella_ensure_runtime_dirs

report_http() {
  local name="$1" code="$2" restricted_ok="${3:-0}"
  if [[ "$code" == 2* ]]; then
    printf '%-14s CONNECTED HTTP=%s\n' "$name" "$code"
  elif [[ "$restricted_ok" == 1 && "$code" == 403 ]]; then
    printf '%-14s CONFIGURED RESTRICTED HTTP=403\n' "$name"
  else
    printf '%-14s DEGRADED  HTTP=%s\n' "$name" "${code:-000}"
  fi
}

not_configured() { printf '%-14s NOT_CONFIGURED\n' "$1"; }
configured() { printf '%-14s CONFIGURED%s\n' "$1" "${2:+ $2}"; }
needs_locator() { printf '%-14s NEEDS_LOCATOR %s\n' "$1" "$2"; }

curl_config_header() {
  local name="$1" url="$2" restricted_ok="$3"; shift 3
  local cfg body code header
  cfg="$(mktemp "$BIELLA_RUNTIME_ROOT/tmp/curl.XXXXXX")"
  body="$(mktemp "$BIELLA_RUNTIME_ROOT/tmp/provider.XXXXXX")"
  chmod 600 "$cfg" "$body"
  {
    printf 'silent\nshow-error\nconnect-timeout = 4\nmax-time = 20\n'
    printf 'output = "%s"\nwrite-out = "%%{http_code}"\n' "$body"
    printf 'url = "%s"\n' "$url"
    for header in "$@"; do
      printf 'header = "%s"\n' "$header"
    done
  } > "$cfg"
  code="$(curl --config "$cfg" 2>/dev/null || true)"
  rm -f -- "$cfg" "$body"
  report_http "$name" "$code" "$restricted_ok"
}

curl_config_basic() {
  local name="$1" url="$2" userpass="$3" restricted_ok="${4:-0}"
  local cfg body code
  cfg="$(mktemp "$BIELLA_RUNTIME_ROOT/tmp/curl.XXXXXX")"
  body="$(mktemp "$BIELLA_RUNTIME_ROOT/tmp/provider.XXXXXX")"
  chmod 600 "$cfg" "$body"
  {
    printf 'silent\nshow-error\nconnect-timeout = 4\nmax-time = 20\n'
    printf 'output = "%s"\nwrite-out = "%%{http_code}"\n' "$body"
    printf 'url = "%s"\nuser = "%s"\n' "$url" "$userpass"
  } > "$cfg"
  code="$(curl --config "$cfg" 2>/dev/null || true)"
  rm -f -- "$cfg" "$body"
  report_http "$name" "$code" "$restricted_ok"
}
if [[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" && -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  curl_config_header Cloudflare "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/models/search" 0 \
    "Authorization: Bearer $CLOUDFLARE_API_TOKEN"
else
  not_configured Cloudflare
fi

[[ -n "${GROQ_API_KEY:-}" ]] && curl_config_header Groq 'https://api.groq.com/openai/v1/models' 0 "Authorization: Bearer $GROQ_API_KEY" || not_configured Groq
[[ -n "${CEREBRAS_API_KEY:-}" ]] && curl_config_header Cerebras 'https://api.cerebras.ai/v1/models' 0 "Authorization: Bearer $CEREBRAS_API_KEY" || not_configured Cerebras
[[ -n "${OPENROUTER_API_KEY:-}" ]] && curl_config_header OpenRouter 'https://openrouter.ai/api/v1/models' 0 "Authorization: Bearer $OPENROUTER_API_KEY" || not_configured OpenRouter
[[ -n "${MISTRAL_API_KEY:-}" ]] && curl_config_header Mistral 'https://api.mistral.ai/v1/models' 0 "Authorization: Bearer $MISTRAL_API_KEY" || not_configured Mistral
[[ -n "${TAVILY_API_KEY:-}" ]] && curl_config_header Tavily 'https://api.tavily.com/usage' 0 "Authorization: Bearer $TAVILY_API_KEY" || not_configured Tavily

if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  curl_config_header Gemini 'https://generativelanguage.googleapis.com/v1beta/models' 0 "x-goog-api-key: $GEMINI_API_KEY"
else
  not_configured Gemini
fi

[[ -n "${EXA_API_KEY:-}" ]] && configured Exa 'NO_LIVE_PROBE' || not_configured Exa
[[ -n "${PINECONE_API_KEY:-}" ]] && curl_config_header Pinecone 'https://api.pinecone.io/indexes' 0 \
  "Api-Key: $PINECONE_API_KEY" 'X-Pinecone-Api-Version: 2026-04' || not_configured Pinecone
if [[ -n "${QDRANT_API_KEY:-}" ]]; then
  if [[ -n "${QDRANT_URL:-}" ]]; then
    curl_config_header Qdrant "${QDRANT_URL%/}/collections" 0 "api-key: $QDRANT_API_KEY"
  else
    needs_locator Qdrant QDRANT_URL
  fi
else
  not_configured Qdrant
fi

[[ -n "${DEEPGRAM_API_KEY:-}" ]] && curl_config_header Deepgram 'https://api.deepgram.com/v1/projects' 0 \
  "Authorization: Token $DEEPGRAM_API_KEY" || not_configured Deepgram
[[ -n "${ASSEMBLYAI_API_KEY:-}" ]] && curl_config_header AssemblyAI 'https://api.assemblyai.com/v2/transcript?limit=1' 0 \
  "Authorization: $ASSEMBLYAI_API_KEY" || not_configured AssemblyAI
[[ -n "${ELEVENLABS_API_KEY:-}" ]] && curl_config_header ElevenLabs 'https://api.elevenlabs.io/v1/models' 0 \
  "xi-api-key: $ELEVENLABS_API_KEY" || not_configured ElevenLabs
[[ -n "${STABILITY_API_KEY:-}" ]] && curl_config_header StabilityAI 'https://api.stability.ai/v1/user/account' 0 \
  "Authorization: Bearer $STABILITY_API_KEY" || not_configured StabilityAI

if [[ -n "${SUPABASE_PUBLISHABLE_KEY:-}" ]]; then
  if [[ -n "${SUPABASE_URL:-}" ]]; then
    curl_config_header Supabase "${SUPABASE_URL%/}/rest/v1/" 0 "apikey: $SUPABASE_PUBLISHABLE_KEY"
  else
    needs_locator Supabase SUPABASE_URL
  fi
else
  not_configured Supabase
fi
[[ -n "${NEON_API_KEY:-}" ]] && curl_config_header Neon 'https://console.neon.tech/api/v2/users/me' 0 \
  "Authorization: Bearer $NEON_API_KEY" || not_configured Neon

if [[ -n "${UPSTASH_API_KEY:-}" ]]; then
  if [[ -n "${UPSTASH_EMAIL:-}" ]]; then
    curl_config_basic Upstash 'https://api.upstash.com/v2/redis/databases' "$UPSTASH_EMAIL:$UPSTASH_API_KEY"
  else
    needs_locator Upstash UPSTASH_EMAIL
  fi
else
  not_configured Upstash
fi

if [[ -n "${CLOUDINARY_API_KEY:-}" && -n "${CLOUDINARY_API_SECRET:-}" ]]; then
  if [[ -n "${CLOUDINARY_CLOUD_NAME:-}" ]]; then
    curl_config_basic Cloudinary "https://api.cloudinary.com/v1_1/${CLOUDINARY_CLOUD_NAME}/ping" \
      "$CLOUDINARY_API_KEY:$CLOUDINARY_API_SECRET"
  else
    needs_locator Cloudinary CLOUDINARY_CLOUD_NAME
  fi
else
  not_configured Cloudinary
fi

[[ -n "${AXIOM_API_TOKEN:-}" ]] && curl_config_header Axiom 'https://api.axiom.co/v2/tokens' 1 \
  "Authorization: Bearer $AXIOM_API_TOKEN" || not_configured Axiom
[[ -n "${PEXELS_API_KEY:-}" ]] && curl_config_header Pexels 'https://api.pexels.com/v1/curated?per_page=1' 0 \
  "Authorization: $PEXELS_API_KEY" || not_configured Pexels
if command -v modal >/dev/null 2>&1 && modal token info >/dev/null 2>&1; then
  printf '%-14s CONNECTED\n' Modal
else
  printf '%-14s DEGRADED\n' Modal
fi

if command -v codex >/dev/null 2>&1 && codex mcp list 2>/dev/null | grep -qi '^saturn .*enabled'; then
  printf '%-14s CONNECTED\n' Saturn
else
  printf '%-14s DEGRADED\n' Saturn
fi
