#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/ops/control_gateway"
MAIN="$DIR/minitz_control_main.py"
GATEWAY="$DIR/minitz_control_gateway.py"
LIVE="$DIR/minitz_live_projection.py"
BASE="$DIR/minitz_base_projection.py"
SERVICE="$DIR/minitz-control-gateway.service"
INSTALLER="$DIR/install-minitz-control-gateway.sh"
AUTH_WRAPPER="$DIR/minitz-control-auth"
TUNNEL_TOKEN_WRAPPER="$DIR/minitz-control-cloudflare-token"
TUNNEL_CONFIG="$DIR/configure-minitz-control-tunnel.sh"
for f in "$MAIN" "$GATEWAY" "$LIVE" "$BASE" "$SERVICE" "$INSTALLER" "$AUTH_WRAPPER" "$TUNNEL_TOKEN_WRAPPER" "$TUNNEL_CONFIG"; do
  [[ -f "$f" ]] || { echo "missing control gateway artifact: $f" >&2; exit 1; }
done
require(){ grep -Fq -- "$2" "$1" || { echo "missing literal in $1: $2" >&2; exit 1; }; }
forbid(){ ! grep -Fq -- "$2" "$1" || { echo "forbidden literal in $1: $2" >&2; exit 1; }; }
require "$MAIN" '127.0.0.1'
require "$MAIN" '8787'
require "$GATEWAY" '/live-api/asset'
require "$BASE" 'STALE_AFTER_SECONDS'
require "$LIVE" 'READ_ONLY_OBSERVER'
forbid "$LIVE" '/usr/local/bin/minitz-codex'
require "$MAIN" '/root/attached-storage/minitz-os-sandbox/state/control/site'
require "$MAIN" '/root/attached-storage/minitz-os-sandbox/state/credentials/control/auth.json'
require "$MAIN" '/root/attached-storage/minitz-os-sandbox/workspace/repo'
require "$MAIN" 'MINITZ_RUNTIME_ROOT'
require "$SERVICE" 'RequiresMountsFor=/root/attached-storage'
require "$SERVICE" 'MINITZ_CONTROL_REPO=/root/attached-storage/minitz-os-sandbox/workspace/repo'
require "$SERVICE" 'MINITZ_CONTROL_STATIC_ROOT=/root/attached-storage/minitz-os-sandbox/state/control/site'
require "$SERVICE" 'MINITZ_CONTROL_AUTH_FILE=/root/attached-storage/minitz-os-sandbox/state/credentials/control/auth.json'
require "$SERVICE" 'ExecStart=/usr/bin/python3 /usr/local/lib/minitz-control/minitz_control_main.py'
require "$INSTALLER" '/usr/local/lib/minitz-control'
require "$INSTALLER" '/root/attached-storage/minitz-os-sandbox/state/control/site'
require "$INSTALLER" '/root/attached-storage/minitz-os-sandbox/state/credentials/control'
require "$INSTALLER" 'minitz-control-gateway.service'
require "$INSTALLER" 'control_active'
require "$INSTALLER" 'control_enablement'
for f in "$MAIN" "$GATEWAY" "$LIVE" "$SERVICE" "$INSTALLER"; do forbid "$f" 'biella'; done
forbid "$INSTALLER" 'CLOUDFLARE_API_TOKEN='
forbid "$INSTALLER" 'password='
bash -n "$INSTALLER"
bash -n "$AUTH_WRAPPER"
bash -n "$TUNNEL_TOKEN_WRAPPER"
bash -n "$TUNNEL_CONFIG"
echo 'control gateway service contract: PASS'
