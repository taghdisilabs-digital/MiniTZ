#!/usr/bin/env bash
set -Eeuo pipefail
SANDBOX="${MINITZ_OS_SANDBOX_ROOT:-/root/attached-storage/minitz-os-sandbox}"
RUNTIME="${MINITZ_RUNTIME_ROOT:-/mnt/biella-extra/biella-runtime/codex-production}"
NAME=minitz-os-lab
MEMORY_ARGS=()
[[ -z "${MINITZ_SANDBOX_MEMORY:-}" ]] || MEMORY_ARGS=(--memory "$MINITZ_SANDBOX_MEMORY" --memory-swap "$MINITZ_SANDBOX_MEMORY")
case "${1:-status}" in
  on)
    if docker container inspect "$NAME" >/dev/null 2>&1; then
      [[ "$(docker inspect -f '{{index .Config.Labels "io.minitz.product"}}' "$NAME")" == 'MiniTZ OS' ]] || exit 2
      exec docker start "$NAME"
    fi
    MODE="${MINITZ_LOCAL_AI_MODE:-auto}"
    NETWORK=()
    if [[ "$MODE" == auto ]]; then
      if python3 -c 'import json,urllib.request; d=json.load(urllib.request.urlopen("http://127.0.0.1:11434/api/ps",timeout=2)); raise SystemExit(0 if any(r.get("name")=="qwen3-coder-next:biella" for r in d.get("models",[])) else 1)' 2>/dev/null; then
        MODE=resident-resource
      else
        MODE=owned
      fi
    fi
    [[ "$MODE" == owned || "$MODE" == resident-resource ]] || exit 2
    [[ "$MODE" != resident-resource ]] || NETWORK=(--network host)
    CODER=/usr/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex
    CODER_AUTH="$(python3 - <<'AUTH'
import json
from pathlib import Path
root=Path('/mnt/biella-extra/biella-runtime/codex-accounts')
active=json.loads((root/'pool-state.json').read_text())['active_account']
row=next(x for x in json.loads((root/'accounts.json').read_text())['accounts'] if x['account_id']==active and x.get('enabled'))
path=Path(row['home'])/'auth.json'
assert path.is_file(), 'Active credential reference unavailable'
print(path)
AUTH
)"
    test -x "$CODER"
    CODER_DIR="$(dirname "$CODER")"
    test -x "$CODER_DIR/codex-code-mode-host"
    test -f "$CODER_AUTH"
    test -f /root/.config/biella-control/auth.json
    test -d /var/lib/biella-control/site
    install -d -m 700 "$SANDBOX/state/runtime/codex"
    INSTALL_MOUNTS=()
    STARTUP=(python3 /workspace/repo/ops/workstation/minitz-os-sandbox/startup.py)
    if [[ -L "$SANDBOX/system/current" ]]; then
      test -f "$SANDBOX/system/current/etc/minitz/source.json"
      INSTALL_MOUNTS=(-v "$SANDBOX/system/current/opt/minitz/source:/opt/minitz/source:ro"
                      -v "$SANDBOX/system/current/etc/minitz:/etc/minitz:ro"
                      -v "$SANDBOX/system/current/usr/bin/minitz:/usr/bin/minitz:ro")
      STARTUP=(/usr/bin/minitz serve)
    fi
    exec docker run --detach --name "$NAME" --label 'io.minitz.product=MiniTZ OS' \
      "${NETWORK[@]}" "${INSTALL_MOUNTS[@]}" --gpus all --runtime=nvidia --hostname minitz-os-lab --init \
      "${MEMORY_ARGS[@]}" --shm-size 1g \
      -v "$SANDBOX/workspace:/workspace:rw" -v "$SANDBOX/state:/state:rw" -v "$SANDBOX/output:/output:rw" \
      -v "$SANDBOX/workspace:$SANDBOX/workspace:rw" -v "$RUNTIME:$RUNTIME:rw" \
      -v "$SANDBOX/workspace/repo/ops/workstation/minitz-os-sandbox/resource-cli.sh:/usr/local/bin/biella:ro" \
-e MINITZ_COMMANDER_AUTOLAUNCH=1 -e VIRTUAL_ENV=/state/validation/startup-foundation-venv \
      -v "$SANDBOX/workspace/repo/ops/workstation/minitz-os-sandbox/environment.sh:/etc/profile.d/minitz-runtime.sh:ro" \
      -e MINITZ_PRODUCTION_AUTORUN=1 -e "MINITZ_DEVELOPMENT_ROOT=$SANDBOX/workspace/repo" \
      -e "BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT=$RUNTIME" \
      -e MINITZ_TASK_PROGRAM_PATH=/root/biella/analysis/live_audit/TASK_PROGRAM.json \
      -e MINITZ_PRODUCTION_PYTHON=/state/validation/startup-foundation-venv/bin/python \
      -e BIELLA_CODEX_BIN=/resources/codex-bin/codex -e CODEX_HOME=/state/runtime/codex \
      -v /usr/local/bin/ollama:/usr/local/bin/ollama:ro \
      -v /usr/local/lib/ollama:/usr/local/lib/ollama:ro \
      -v /usr/share/ollama/.ollama/models:/resources/models:ro \
      -v /root/biella/analysis/live_audit:/root/biella/analysis/live_audit:rw \
      -v "$RUNTIME/memory/compacted-memory.json:/minitz-live/compacted-memory.json:ro" \
      -v "$RUNTIME/memory/current-task.json:/minitz-live/current-task.json:ro" \
      -v "$CODER_DIR:/resources/codex-bin:ro" \
      -v "$CODER_AUTH:/state/runtime/codex/auth.json:ro" \
      -v /var/lib/biella-control/site:/resources/control-site:ro \
      -v /root/.config/biella-control/auth.json:/resources/credentials/control-auth.json:ro \
      -e "MINITZ_LOCAL_AI_MODE=$MODE" -e HOME=/state/runtime/home -e OLLAMA_MODELS=/resources/models \
      -e OLLAMA_HOST=127.0.0.1:11434 -e OLLAMA_CONTEXT_LENGTH=16384 \
      -e OLLAMA_NUM_PARALLEL=1 -e OLLAMA_MAX_LOADED_MODELS=1 \
      -e OLLAMA_FLASH_ATTENTION=1 -e OLLAMA_KV_CACHE_TYPE=q8_0 -e OLLAMA_KEEP_ALIVE=-1 \
      -e PYTHONDONTWRITEBYTECODE=1 -e BIELLA_OLLAMA_URL=http://127.0.0.1:11434 \
      minitz-os-lab:ubuntu26.04 "${STARTUP[@]}"
    ;;
  off)
    if docker container inspect "$NAME" >/dev/null 2>&1; then
      [[ "$(docker inspect -f '{{index .Config.Labels "io.minitz.product"}}' "$NAME")" == 'MiniTZ OS' ]] || exit 2
      docker stop --timeout -1 "$NAME"
      docker rm "$NAME"
    fi
    ;;
  status) docker inspect --format '{{json .State}}' "$NAME" ;;
  exec) shift; exec docker exec "$NAME" "$@" ;;
  *) echo 'usage: runtime.sh {on|off|status|exec command...}' >&2; exit 2 ;;
esac
