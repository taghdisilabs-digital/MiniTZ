#!/usr/bin/env bash
set -Eeuo pipefail

OLLAMA_URL="${MINITZ_OLLAMA_URL:-http://127.0.0.1:11434}"
MODEL="${MINITZ_QWEN_MODEL:-qwen3-coder-next:minitz}"
INTERVAL="${MINITZ_QWEN_RESIDENCY_INTERVAL_SECONDS:-30}"

desired_digest() {
  curl -fsS --connect-timeout 2 --max-time 5 "$OLLAMA_URL/api/tags" 2>/dev/null |
    python3 -c 'import json,sys; m=sys.argv[1]; d=json.load(sys.stdin); x=next((r for r in d.get("models",[]) if r.get("name")==m or r.get("model")==m),None); raise SystemExit(1) if not x or not x.get("digest") else print(x["digest"])' "$MODEL"
}

model_loaded() {
  local digest
  digest="$(desired_digest)" || return 1
  curl -fsS --connect-timeout 2 --max-time 5 "$OLLAMA_URL/api/ps" 2>/dev/null |
    python3 -c 'import json,sys; digest=sys.argv[1]; d=json.load(sys.stdin); raise SystemExit(0 if any(r.get("digest")==digest and int(r.get("size_vram") or 0)>0 for r in d.get("models",[])) else 1)' "$digest" >/dev/null 2>&1
}

ollama_ready() {
  curl -fsS --connect-timeout 2 --max-time 5 "$OLLAMA_URL/api/tags" >/dev/null 2>&1
}

warm_model() {
  local payload
  payload="$(python3 - "$MODEL" <<'PY'
import json,sys
print(json.dumps({"model":sys.argv[1],"prompt":"","stream":False,"keep_alive":-1},separators=(",",":")))
PY
)"
  curl -fsS --connect-timeout 3 --max-time 900 -H 'Content-Type: application/json' --data-binary "$payload" "$OLLAMA_URL/api/generate" >/dev/null 2>&1
}

while true; do
  if ollama_ready && ! model_loaded; then
    warm_model || true
  fi
  sleep "$INTERVAL"
done
