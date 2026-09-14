#!/usr/bin/env bash
set -Eeuo pipefail

OLLAMA_URL="${BIELLA_OLLAMA_URL:-http://127.0.0.1:11434}"
MODEL="${BIELLA_QWEN_MODEL:-qwen3-coder-next:biella}"
INTERVAL="${BIELLA_QWEN_RESIDENCY_INTERVAL_SECONDS:-30}"
NUM_GPU="${BIELLA_QWEN_NUM_GPU:-42}"
NUM_CTX="${BIELLA_QWEN_NUM_CTX:-16384}"

model_loaded() {
  curl -fsS --connect-timeout 2 --max-time 5 "$OLLAMA_URL/api/ps" 2>/dev/null |
    python3 -c 'import json,sys; m=sys.argv[1]; d=json.load(sys.stdin); raise SystemExit(0 if any(x.get("name")==m or x.get("model")==m for x in d.get("models",[])) else 1)' "$MODEL" >/dev/null 2>&1
}

model_profile_matches() {
  python3 - "$NUM_GPU" "$NUM_CTX" <<'PY2'
import os, pathlib, sys
want_gpu=str(int(sys.argv[1])); want_ctx=str(int(sys.argv[2]))
for path in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
    try:
        raw=path.read_bytes()
    except OSError:
        continue
    args=[x.decode(errors='replace') for x in raw.split(b'\0') if x]
    if not args or os.path.basename(args[0]) != 'llama-server':
        continue
    def value(flag):
        try:
            return args[args.index(flag)+1]
        except (ValueError, IndexError):
            return None
    if value('-ngl') == want_gpu and value('-c') == want_ctx:
        raise SystemExit(0)
raise SystemExit(1)
PY2
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

unload_model() {
  local payload
  payload="$(python3 - "$MODEL" <<'PY'
import json,sys
print(json.dumps({"model":sys.argv[1],"prompt":"","stream":False,"keep_alive":0},separators=(",",":")))
PY
)"
  curl -fsS --connect-timeout 3 --max-time 120 -H 'Content-Type: application/json' --data-binary "$payload" "$OLLAMA_URL/api/generate" >/dev/null 2>&1
}

while true; do
  if ollama_ready; then
    if ! model_loaded; then
      warm_model || true
    elif ! model_profile_matches; then
      unload_model || true
      warm_model || true
    fi
  fi
  sleep "$INTERVAL"
done
