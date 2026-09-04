#!/usr/bin/env bash
set -Eeuo pipefail
RUNTIME=/root/.config/biella-ai/runtime.env
install -d -m 700 /root/.config/biella-ai
touch "$RUNTIME"
chmod 600 "$RUNTIME"
chown root:root "$RUNTIME"

read_secret() {
  local label="$1" var="$2"
  local value
  read -rsp "$label: " value
  echo
  printf -v "$var" '%s' "$value"
}

read_secret 'Cloudflare Workers AI token' CLOUDFLARE_API_TOKEN_NEW
read_secret 'Groq API key' GROQ_API_KEY_NEW
read_secret 'Cerebras API key' CEREBRAS_API_KEY_NEW
read_secret 'OpenRouter API key' OPENROUTER_API_KEY_NEW
read_secret 'Mistral API key' MISTRAL_API_KEY_NEW
read_secret 'Tavily API key' TAVILY_API_KEY_NEW

export RUNTIME CLOUDFLARE_API_TOKEN_NEW GROQ_API_KEY_NEW CEREBRAS_API_KEY_NEW OPENROUTER_API_KEY_NEW MISTRAL_API_KEY_NEW TAVILY_API_KEY_NEW
python3 - <<'PY'
from pathlib import Path
import os, shlex
path = Path(os.environ['RUNTIME'])
updates = {
    'CLOUDFLARE_API_TOKEN': os.environ['CLOUDFLARE_API_TOKEN_NEW'],
    'GROQ_API_KEY': os.environ['GROQ_API_KEY_NEW'],
    'CEREBRAS_API_KEY': os.environ['CEREBRAS_API_KEY_NEW'],
    'OPENROUTER_API_KEY': os.environ['OPENROUTER_API_KEY_NEW'],
    'MISTRAL_API_KEY': os.environ['MISTRAL_API_KEY_NEW'],
    'TAVILY_API_KEY': os.environ['TAVILY_API_KEY_NEW'],
}
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

unset CLOUDFLARE_API_TOKEN_NEW GROQ_API_KEY_NEW CEREBRAS_API_KEY_NEW OPENROUTER_API_KEY_NEW MISTRAL_API_KEY_NEW TAVILY_API_KEY_NEW RUNTIME
chmod 600 /root/.config/biella-ai/runtime.env
chown root:root /root/.config/biella-ai/runtime.env
echo 'Provider credentials saved.'ask_secret SUPABASE_PUBLISHABLE_KEY 'Supabase publishable key'
ask_plain SUPABASE_URL 'Supabase project URL'
ask_secret NEON_API_KEY 'Neon API key'
ask_secret UPSTASH_API_KEY 'Upstash API key'
ask_plain UPSTASH_EMAIL 'Upstash account email'
ask_secret CLOUDINARY_API_KEY 'Cloudinary API key'
ask_secret CLOUDINARY_API_SECRET 'Cloudinary API secret'
ask_plain CLOUDINARY_CLOUD_NAME 'Cloudinary cloud name'
ask_secret AXIOM_API_TOKEN 'Axiom API token'
ask_secret PEXELS_API_KEY 'Pexels API key'

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

unset RUNTIME updates_file
chmod 600 "$RUNTIME" 2>/dev/null || true
chown root:root "$RUNTIME" 2>/dev/null || true
printf 'Provider configuration updated.\n'
