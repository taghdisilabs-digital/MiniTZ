#!/usr/bin/env bash
set -Eeuo pipefail

OLLAMA_URL="${BIELLA_OLLAMA_URL:-http://127.0.0.1:11434}"
MODEL="${BIELLA_QWEN_MODEL:-qwen3-coder-next:biella}"
INTERVAL="${BIELLA_QWEN_RESIDENCY_INTERVAL_SECONDS:-30}"
NUM_GPU="${BIELLA_QWEN_NUM_GPU:-34}"
NUM_CTX="${BIELLA_QWEN_NUM_CTX:-16384}"

model_loaded() {
  curl -fsS --connect-timeout 2 --max-time 5 "$OLLAMA_URL/api/ps" 2>/dev/null |
    python3 -c 'import json,sys; m=sys.argv[1]; d=json.load(sys.stdin); raise SystemExit(0 if any(x.get("name")==m or x.get("model")==m for x in d.get("models",[])) else 1)' "$MODEL" >/dev/null 2>&1
}

ollama_ready() {
  curl -fsS --connect-timeout 2 --max-time 5 "$OLLAMA_URL/api/tags" >/dev/null 2>&1
}

warm_model() {
  local payload
  payload="$(python3 - "$MODEL" "$NUM_GPU" "$NUM_CTX" <<'PY'
import json,sys
print(json.dumps({"model":sys.argv[1],"prompt":"","stream":False,"keep_alive":-1,"options":{"num_gpu":int(sys.argv[2]),"num_ctx":int(sys.argv[3])}},separators=(",",":")))
PY
)"
  curl -fsS --connect-timeout 3 --max-time 900 -H 'Content-Type: application/json' --data-binary "$payload" "$OLLAMA_URL/api/generate" >/dev/null 2>&1
}

while true; do
  if ! model_loaded && ollama_ready; then
    warm_model || true
  fi
  sleep "$INTERVAL"
done
