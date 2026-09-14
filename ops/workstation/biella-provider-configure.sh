#!/usr/bin/env bash
set -Eeuo pipefail

readonly RUNTIME="${BIELLA_AI_RUNTIME_ENV:-/root/.config/biella-ai/runtime.env}"
install -d -o root -g root -m 700 "$(dirname "$RUNTIME")"
touch "$RUNTIME"
chown root:root "$RUNTIME"
chmod 600 "$RUNTIME"

set -a
# shellcheck disable=SC1090
source "$RUNTIME"
set +a

updates_file="$(mktemp /tmp/biella-provider-updates.XXXXXX)"
chmod 600 "$updates_file"
trap '[[ -z "${updates_file:-}" ]] || rm -f -- "$updates_file"' EXIT

queue_value() {
  local key="$1" value="$2"
  [[ -n "$value" ]] || return 0
  printf '%s\0%s\0' "$key" "$value" >> "$updates_file"
}

ask_secret() {
  local key="$1" label="$2" current value suffix=''
  current="${!key:-}"
  [[ -n "$current" ]] && suffix=' [configured; Enter keeps]'
  read -rsp "$label$suffix: " value
  printf '\n'
  queue_value "$key" "$value"
}
ask_plain() {
  local key="$1" label="$2" current value suffix=''
  current="${!key:-}"
  [[ -n "$current" ]] && suffix=" [configured: $current; Enter keeps]"
  read -rp "$label$suffix: " value
  queue_value "$key" "$value"
}

printf 'Biella provider configuration. Enter keeps existing values.\n'
ask_secret CLOUDFLARE_API_TOKEN 'Cloudflare Workers AI token'
ask_secret GROQ_API_KEY 'Groq API key'
ask_secret CEREBRAS_API_KEY 'Cerebras API key'
ask_secret OPENROUTER_API_KEY 'OpenRouter API key'
ask_secret MISTRAL_API_KEY 'Mistral API key'
ask_secret TAVILY_API_KEY 'Tavily API key'
ask_secret GEMINI_API_KEY 'Gemini API key'
ask_secret BIELLA_GOOGLE_API_KEY 'General Google API key'
ask_secret EXA_API_KEY 'Exa API key'
ask_secret PINECONE_API_KEY 'Pinecone API key'
ask_secret QDRANT_API_KEY 'Qdrant API key'
ask_plain QDRANT_URL 'Qdrant cluster URL'
ask_secret DEEPGRAM_API_KEY 'Deepgram API key'
ask_secret ASSEMBLYAI_API_KEY 'AssemblyAI API key'
ask_secret ELEVENLABS_API_KEY 'ElevenLabs API key'
ask_secret STABILITY_API_KEY 'Stability AI API key'
ask_secret SUPABASE_PUBLISHABLE_KEY 'Supabase publishable key'
ask_plain SUPABASE_URL 'Supabase project URL'
ask_secret NEON_API_KEY 'Neon API key'
ask_secret UPSTASH_API_KEY 'Upstash API key'
ask_plain UPSTASH_EMAIL 'Upstash account email'
ask_secret CLOUDINARY_API_KEY 'Cloudinary API key'
ask_secret CLOUDINARY_API_SECRET 'Cloudinary API secret'
ask_plain CLOUDINARY_CLOUD_NAME 'Cloudinary cloud name'
ask_secret AXIOM_API_TOKEN 'Axiom API token'
ask_secret PEXELS_API_KEY 'Pexels API key'
ask_secret NVIDIA_API_KEY 'NVIDIA API key'

export RUNTIME updates_file
python3 - <<'PY'
from pathlib import Path
import os, shlex
path = Path(os.environ['RUNTIME'])
raw = Path(os.environ['updates_file']).read_bytes().split(b'\0')
items = [x.decode('utf-8') for x in raw if x]
updates = dict(zip(items[0::2], items[1::2]))
lines = path.read_text().splitlines() if path.exists() else []
out, seen = [], set()
for line in lines:
    key = line.split('=', 1)[0] if '=' in line else ''
    if key in updates:
        out.append(f"{key}={shlex.quote(updates[key])}")
        seen.add(key)
    else:
        out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={shlex.quote(value)}")
tmp = path.with_name(path.name + '.tmp')
tmp.write_text('\n'.join(out) + '\n')
tmp.chmod(0o600)
tmp.replace(path)
PY

chmod 600 "$RUNTIME"
chown root:root "$RUNTIME"
printf 'Provider configuration updated.\n'
