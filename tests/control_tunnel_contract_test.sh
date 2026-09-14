#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/ops/control_gateway"
SCRIPT="$DIR/configure-minitz-control-tunnel.sh"
SERVICE="$DIR/minitz-control-tunnel.service"
TOKEN_SCRIPT="$DIR/minitz-control-cloudflare-token"
for f in "$SCRIPT" "$SERVICE" "$TOKEN_SCRIPT"; do [[ -f "$f" ]] || { echo "missing tunnel artifact: $f" >&2; exit 1; }; done
req() { grep -Fq -- "$2" "$1" || { echo "missing tunnel literal in $1: $2" >&2; exit 1; }; }
forbid() { ! grep -Fq -- "$2" "$1" || { echo "forbidden tunnel literal in $1: $2" >&2; exit 1; }; }
req "$SCRIPT" 'control.minitzgames.dev'
req "$SCRIPT" 'minitz-control'
req "$SCRIPT" '127.0.0.1:8787'
req "$SCRIPT" 'cfargotunnel.com'
req "$SCRIPT" 'CLOUDFLARE_ACCOUNT_ID'
req "$SCRIPT" 'CLOUDFLARE_TUNNEL_API_TOKEN'
req "$SCRIPT" 'CLOUDFLARE_API_TOKEN'
req "$SCRIPT" 'conflicting DNS record'
req "$TOKEN_SCRIPT" 'CLOUDFLARE_TUNNEL_API_TOKEN'
req "$TOKEN_SCRIPT" 'read -rsp'
req "$TOKEN_SCRIPT" '/root/.config/minitz-ai/runtime.env'
req "$SERVICE" '/etc/cloudflared/minitz-control.yml'
req "$SERVICE" 'minitz-control-gateway.service'
forbid "$SCRIPT" 'minitzgames.dev/deployment.json'
forbid "$SCRIPT" 'CLOUDFLARE_API_TOKEN='
forbid "$TOKEN_SCRIPT" 'CLOUDFLARE_API_TOKEN='
bash -n "$SCRIPT"
bash -n "$TOKEN_SCRIPT"
echo 'control tunnel contract: PASS'
