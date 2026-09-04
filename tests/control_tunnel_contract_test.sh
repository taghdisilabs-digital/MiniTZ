#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/ops/control_gateway"
SCRIPT="$DIR/configure-biella-control-tunnel.sh"
SERVICE="$DIR/biella-control-tunnel.service"
TOKEN_SCRIPT="$DIR/biella-control-cloudflare-token"
for f in "$SCRIPT" "$SERVICE" "$TOKEN_SCRIPT"; do [[ -f "$f" ]] || { echo "missing tunnel artifact: $f" >&2; exit 1; }; done
req() { grep -Fq -- "$2" "$1" || { echo "missing tunnel literal in $1: $2" >&2; exit 1; }; }
forbid() { ! grep -Fq -- "$2" "$1" || { echo "forbidden tunnel literal in $1: $2" >&2; exit 1; }; }
req "$SCRIPT" 'control.biellagames.dev'
req "$SCRIPT" 'biella-control'
req "$SCRIPT" '127.0.0.1:8787'
req "$SCRIPT" 'cfargotunnel.com'
req "$SCRIPT" 'CLOUDFLARE_ACCOUNT_ID'
req "$SCRIPT" 'CLOUDFLARE_TUNNEL_API_TOKEN'
req "$SCRIPT" 'CLOUDFLARE_API_TOKEN'
req "$SCRIPT" 'conflicting DNS record'
req "$TOKEN_SCRIPT" 'CLOUDFLARE_TUNNEL_API_TOKEN'
req "$TOKEN_SCRIPT" 'read -rsp'
req "$TOKEN_SCRIPT" '/root/.config/biella-ai/runtime.env'
req "$SERVICE" '/etc/cloudflared/biella-control.yml'
req "$SERVICE" 'biella-control-gateway.service'
forbid "$SCRIPT" 'biellagames.dev/deployment.json'
forbid "$SCRIPT" 'CLOUDFLARE_API_TOKEN='
forbid "$TOKEN_SCRIPT" 'CLOUDFLARE_API_TOKEN='
bash -n "$SCRIPT"
bash -n "$TOKEN_SCRIPT"
echo 'control tunnel contract: PASS'
