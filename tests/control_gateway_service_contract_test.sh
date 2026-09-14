#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/ops/control_gateway"
MAIN="$DIR/minitz_control_main.py"
LIVE="$DIR/minitz_live_projection.py"
SERVICE="$DIR/minitz-control-gateway.service"
INSTALLER="$DIR/install-minitz-control-gateway.sh"
AUTH_WRAPPER="$DIR/minitz-control-auth"
TUNNEL_TOKEN_WRAPPER="$DIR/minitz-control-cloudflare-token"
TUNNEL_CONFIG="$DIR/configure-minitz-control-tunnel.sh"

for f in "$MAIN" "$LIVE" "$SERVICE" "$INSTALLER" "$AUTH_WRAPPER" "$TUNNEL_TOKEN_WRAPPER" "$TUNNEL_CONFIG"; do
  [[ -f "$f" ]] || { echo "missing control gateway artifact: $f" >&2; exit 1; }
done

require() { grep -Fq -- "$2" "$1" || { echo "missing literal in $1: $2" >&2; exit 1; }; }
forbid() { ! grep -Fq -- "$2" "$1" || { echo "forbidden literal in $1: $2" >&2; exit 1; }; }

require "$MAIN" '127.0.0.1'
require "$MAIN" '8787'
require "$MAIN" 'games-presentation'
require "$LIVE" '/live-api/asset'
require "$LIVE" 'STALE_AFTER_SECONDS'
require "$LIVE" 'READ_ONLY_OBSERVER'
forbid "$LIVE" '/usr/local/bin/minitz-codex'
require "$MAIN" '/var/lib/minitz-control/site'
require "$MAIN" '/root/.config/minitz-control/auth.json'
require "$MAIN" '/root/attached-storage/minitz-os-sandbox/workspace/repo'
forbid "$MAIN" '/root/minitz/repos/minitz-engine'
forbid "$MAIN" '/root/minitz/repos/minitz-games'
require "$SERVICE" 'MINITZ_CONTROL_REPO=/root/attached-storage/minitz-os-sandbox/workspace/repo'
forbid "$SERVICE" 'MINITZ_CONTROL_REPO=/root/minitz/repos/minitz-engine'
forbid "$SERVICE" 'MINITZ_CONTROL_GAMES_REPO'
forbid "$SERVICE" 'MINITZ_CONTROL_WEBSITE_WORKDIR'
require "$SERVICE" 'ExecStart=/usr/bin/python3 /usr/local/lib/minitz-control/minitz_control_main.py'
require "$SERVICE" 'User=root'
require "$SERVICE" 'UMask=0077'
require "$SERVICE" 'RequiresMountsFor=/mnt/minitz-extra'
require "$INSTALLER" '/usr/local/lib/minitz-control'
require "$INSTALLER" '/usr/local/bin/minitz-control-auth'
require "$INSTALLER" '/usr/local/bin/minitz-control-cloudflare-token'
require "$INSTALLER" '/usr/local/bin/minitz-control-tunnel-configure'
require "$INSTALLER" 'configure-minitz-control-tunnel.sh'
require "$INSTALLER" 'minitz-control-tunnel.service'
require "$INSTALLER" '/var/lib/minitz-control/site'
require "$INSTALLER" 'minitz-control-gateway.service'
require "$INSTALLER" 'control_active'
require "$INSTALLER" 'control_enablement'
require "$INSTALLER" 'if [[ "$control_active" == "active" ]]'
require "$INSTALLER" 'systemctl restart minitz-control-gateway.service'
forbid "$INSTALLER" 'systemctl enable --now minitz-control-gateway.service'
require "$AUTH_WRAPPER" 'minitz_control_auth.py'
forbid "$INSTALLER" 'CLOUDFLARE_API_TOKEN='
forbid "$INSTALLER" 'password='

bash -n "$INSTALLER"
bash -n "$AUTH_WRAPPER"
bash -n "$TUNNEL_TOKEN_WRAPPER"
bash -n "$TUNNEL_CONFIG"
echo 'control gateway service contract: PASS'
