#!/usr/bin/env bash
set -Eeuo pipefail

OLLAMA_URL="${MINITZ_OLLAMA_URL:-http://127.0.0.1:11434}"
MODEL="${MINITZ_QWEN_MODEL:-qwen3-coder-next:minitz}"
TIMEOUT="${MINITZ_QWEN_READY_TIMEOUT_SECONDS:-900}"
DEADLINE=$((SECONDS + TIMEOUT))

model_loaded() {
  curl -fsS --connect-timeout 2 --max-time 5 "$OLLAMA_URL/api/ps" 2>/dev/null |
    python3 -c 'import json,sys; m=sys.argv[1]; d=json.load(sys.stdin); raise SystemExit(0 if any((x.get("name")==m or x.get("model")==m) and int(x.get("size_vram") or 0)>0 for x in d.get("models",[])) else 1)' "$MODEL" >/dev/null 2>&1
}

while (( SECONDS < DEADLINE )); do
  if model_loaded; then
    exit 0
  fi
  sleep 1
done

printf 'Qwen residency not confirmed before router startup: %s\n' "$MODEL" >&2
exit 1
