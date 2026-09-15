#!/usr/bin/env bash
set -Eeuo pipefail
SANDBOX="${MINITZ_OS_SANDBOX_ROOT:-/root/attached-storage/minitz-os-sandbox}"
RUNTIME="${MINITZ_RUNTIME_ROOT:-$SANDBOX/state/production}"
NAME=minitz-os-lab
MEMORY_ARGS=()
[[ -z "${MINITZ_SANDBOX_MEMORY:-}" ]] || MEMORY_ARGS=(--memory "$MINITZ_SANDBOX_MEMORY" --memory-swap "$MINITZ_SANDBOX_MEMORY")

ensure_installed_source_matches_workspace() {
  PYTHONPATH="$SANDBOX/workspace/repo/src" python3 - "$SANDBOX/workspace/repo" "$SANDBOX/output/source-releases" "$SANDBOX/system" <<'PYCODE'
import json
import sys
from pathlib import Path
from minitz_os.source import build_release, install_release, recover_installation, source_manifest

workspace = Path(sys.argv[1]).resolve()
release_root = Path(sys.argv[2]).resolve()
system_root = Path(sys.argv[3]).resolve()
expected = source_manifest(workspace)
current = system_root / "current"
matched = False
if current.is_symlink():
    try:
        recovered = recover_installation(system_root)
        matched = recovered["source"]["source_sha256"] == expected["source_sha256"]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        matched = False
if not matched:
    release = build_release(workspace, release_root)
    if release["source_sha256"] != expected["source_sha256"]:
        raise SystemExit("MiniTZ release source identity changed during reconciliation")
    installed = install_release(Path(release["artifact_path"]), system_root, release["artifact_sha256"])
    if installed["source_sha256"] != expected["source_sha256"]:
        raise SystemExit("MiniTZ installed source identity mismatch")
final = recover_installation(system_root)
if final["source"]["source_sha256"] != expected["source_sha256"]:
    raise SystemExit("MiniTZ active installed source is not the current workspace source")
print(expected["source_sha256"])
PYCODE
}
case "${1:-status}" in
  on)
    if docker container inspect "$NAME" >/dev/null 2>&1; then
      [[ "$(docker inspect -f '{{index .Config.Labels "io.minitz.product"}}' "$NAME")" == 'MiniTZ OS' ]] || exit 2
      if [[ "$(docker inspect -f '{{.State.Running}}' "$NAME")" == 'true' ]]; then
        docker stop --timeout -1 "$NAME" >/dev/null
      fi
      docker rm "$NAME" >/dev/null
    fi
    # Exact workspace bytes are packaged by build_release and atomically activated by install_release.
    ensure_installed_source_matches_workspace >/dev/null
    MODE="${MINITZ_LOCAL_AI_MODE:-auto}"
    NETWORK=()
    if [[ "$MODE" == auto ]]; then
      if python3 -c 'import json,urllib.request; p=json.load(urllib.request.urlopen("http://127.0.0.1:11434/api/ps",timeout=2)); t=json.load(urllib.request.urlopen("http://127.0.0.1:11434/api/tags",timeout=2)); desired=next((r.get("digest") for r in t.get("models",[]) if r.get("name")=="qwen3-coder-next:minitz"),None); raise SystemExit(0 if desired and any(r.get("digest")==desired for r in p.get("models",[])) else 1)' 2>/dev/null; then
        MODE=resident-resource
      else
        MODE=owned
      fi
    fi
    [[ "$MODE" == owned || "$MODE" == resident-resource ]] || exit 2
    [[ "$MODE" != resident-resource ]] || NETWORK=(--network host)
    LOCAL_QWEN_PARALLEL="${MINITZ_LOCAL_QWEN_PARALLEL:-}"
    if [[ "$MODE" == resident-resource && -z "$LOCAL_QWEN_PARALLEL" ]]; then
      OLLAMA_PID="$(pgrep -o -x ollama 2>/dev/null || true)"
      if [[ -n "$OLLAMA_PID" && -r "/proc/$OLLAMA_PID/environ" ]]; then
        LOCAL_QWEN_PARALLEL="$(tr '\0' '\n' <"/proc/$OLLAMA_PID/environ" | awk -F= '$1=="OLLAMA_NUM_PARALLEL"{print $2; exit}')"
      fi
    fi
    QWEN_PARALLEL_ENV=()
    [[ -z "$LOCAL_QWEN_PARALLEL" ]] || QWEN_PARALLEL_ENV=(-e "MINITZ_LOCAL_QWEN_PARALLEL=$LOCAL_QWEN_PARALLEL")
    CODER=/usr/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex
    CODER_AUTH="$(python3 - <<'AUTH'
import json
from pathlib import Path
root=Path('/root/attached-storage/minitz-os-sandbox/state/credentials/codex-accounts')
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
    test -f "$SANDBOX/state/credentials/control/auth.json"
    test -f /root/.config/gh/hosts.yml
    test -d "$SANDBOX/state/control/site"
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
      "${NETWORK[@]}" "${QWEN_PARALLEL_ENV[@]}" "${INSTALL_MOUNTS[@]}" --gpus all --runtime=nvidia --hostname minitz-os-lab --init \
      "${MEMORY_ARGS[@]}" --shm-size 1g \
      -v "$SANDBOX/workspace:/workspace:rw" -v "$SANDBOX/state:/state:rw" -v "$SANDBOX/output:/output:rw" \
      -v "$SANDBOX/workspace:$SANDBOX/workspace:rw" -v "$RUNTIME:$RUNTIME:rw" \
      -v "$SANDBOX/workspace/repo/ops/workstation/minitz-os-sandbox/resource-cli.sh:/usr/local/bin/minitz-resource:ro" \
-e MINITZ_COMMANDER_AUTOLAUNCH=1 -e VIRTUAL_ENV=/state/validation/startup-foundation-venv \
      -v "$SANDBOX/workspace/repo/ops/workstation/minitz-os-sandbox/environment.sh:/etc/profile.d/minitz-runtime.sh:ro" \
      -e MINITZ_PRODUCTION_AUTORUN=1 -e "MINITZ_DEVELOPMENT_ROOT=$SANDBOX/workspace/repo" \
      -e "MINITZ_RUNTIME_ROOT=$RUNTIME" \
      -e MINITZ_TASK_PROGRAM_PATH=/state/task-program/TASK_PROGRAM.json \
      -e MINITZ_PRODUCTION_PYTHON=/state/validation/startup-foundation-venv/bin/python \
      -e MINITZ_CODEX_BIN=/resources/codex-bin/codex -e CODEX_HOME=/state/runtime/codex \
      -v /usr/local/bin/ollama:/usr/local/bin/ollama:ro \
      -v /usr/local/lib/ollama:/usr/local/lib/ollama:ro \
      -v /usr/share/ollama/.ollama/models:/resources/models:ro \
      -v "$RUNTIME/memory/compacted-memory.json:/minitz-live/compacted-memory.json:ro" \
      -v "$RUNTIME/memory/current-task.json:/minitz-live/current-task.json:ro" \
      -v "$CODER_DIR:/resources/codex-bin:ro" \
      -v "$CODER_AUTH:/state/runtime/codex/auth.json:ro" \
      -v "$SANDBOX/state/control/site:/resources/control-site:ro" \
      -v "$SANDBOX/state/credentials/control/auth.json:/resources/credentials/control-auth.json:ro" \
      -v /root/.config/gh/hosts.yml:/resources/credentials/github/hosts.yml:ro \
      -v "$SANDBOX/workspace/repo/ops/workstation/minitz-os-sandbox/git-credential-github:/usr/local/bin/minitz-git-credential-github:ro" \
      -e MINITZ_GITHUB_CREDENTIAL_FILE=/resources/credentials/github/hosts.yml \
      -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=credential.helper -e GIT_CONFIG_VALUE_0=/usr/local/bin/minitz-git-credential-github \
      -e "MINITZ_LOCAL_AI_MODE=$MODE" -e HOME=/state/runtime/home -e OLLAMA_MODELS=/resources/models \
      -e OLLAMA_HOST=127.0.0.1:11434 -e OLLAMA_CONTEXT_LENGTH=16384 \
      -e OLLAMA_MAX_LOADED_MODELS=1 \
      -e OLLAMA_FLASH_ATTENTION=1 -e OLLAMA_KV_CACHE_TYPE=q8_0 -e OLLAMA_KEEP_ALIVE=-1 \
      -e PYTHONDONTWRITEBYTECODE=1 -e MINITZ_OLLAMA_URL=http://127.0.0.1:11434 -e MINITZ_LOCAL_MODEL=qwen3-coder-next:minitz \
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
