#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/ops/control_gateway"
MAIN="$DIR/biella_control_main.py"
LIVE="$DIR/biella_live_projection.py"
SERVICE="$DIR/biella-control-gateway.service"
INSTALLER="$DIR/install-biella-control-gateway.sh"
AUTH_WRAPPER="$DIR/biella-control-auth"
TUNNEL_TOKEN_WRAPPER="$DIR/biella-control-cloudflare-token"
TUNNEL_CONFIG="$DIR/configure-biella-control-tunnel.sh"

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
forbid "$LIVE" '/usr/local/bin/biella-codex'
require "$MAIN" '/var/lib/biella-control/site'
require "$MAIN" '/root/.config/biella-control/auth.json'
require "$MAIN" '/root/biella/repos/biella-engine'
forbid "$MAIN" '/root/biella/repos/biella-games'
require "$SERVICE" 'BIELLA_CONTROL_REPO=/root/biella/repos/biella-engine'
forbid "$SERVICE" 'BIELLA_CONTROL_GAMES_REPO'
forbid "$SERVICE" 'BIELLA_CONTROL_WEBSITE_WORKDIR'
require "$SERVICE" 'ExecStart=/usr/bin/python3 /usr/local/lib/biella-control/biella_control_main.py'
require "$SERVICE" 'User=root'
require "$SERVICE" 'UMask=0077'
require "$SERVICE" 'RequiresMountsFor=/mnt/biella-extra'
require "$INSTALLER" '/usr/local/lib/biella-control'
require "$INSTALLER" '/usr/local/bin/biella-control-auth'
require "$INSTALLER" '/usr/local/bin/biella-control-cloudflare-token'
require "$INSTALLER" '/usr/local/bin/biella-control-tunnel-configure'
require "$INSTALLER" 'configure-biella-control-tunnel.sh'
require "$INSTALLER" 'biella-control-tunnel.service'
require "$INSTALLER" '/var/lib/biella-control/site'
require "$INSTALLER" 'biella-control-gateway.service'
require "$AUTH_WRAPPER" 'biella_control_auth.py'
forbid "$INSTALLER" 'CLOUDFLARE_API_TOKEN='
forbid "$INSTALLER" 'password='

bash -n "$INSTALLER"
bash -n "$AUTH_WRAPPER"
bash -n "$TUNNEL_TOKEN_WRAPPER"
bash -n "$TUNNEL_CONFIG"
echo 'control gateway service contract: PASS'
