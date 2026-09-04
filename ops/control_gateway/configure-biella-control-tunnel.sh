#!/usr/bin/env bash
set -Eeuo pipefail

readonly RUNTIME_ENV="${BIELLA_AI_RUNTIME_ENV:-/root/.config/biella-ai/runtime.env}"
readonly API="https://api.cloudflare.com/client/v4"
readonly HOSTNAME="control.biellagames.dev"
readonly TUNNEL_NAME="biella-control"
readonly ORIGIN="http://127.0.0.1:8787"
readonly CONFIG_DIR="/etc/cloudflared"
readonly CONFIG_FILE="$CONFIG_DIR/biella-control.yml"
readonly CONTROL_INSTALL_DIR="${BIELLA_CONTROL_INSTALL_DIR:-/usr/local/lib/biella-control}"
readonly SERVICE_SOURCE="$CONTROL_INSTALL_DIR/biella-control-tunnel.service"

[[ "$EUID" -eq 0 ]] || { echo 'run tunnel configurator as root' >&2; exit 1; }
[[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]] || { echo 'Biella runtime credentials missing' >&2; exit 1; }
[[ "$(stat -c '%u:%a' "$RUNTIME_ENV")" == "0:600" ]] || { echo 'Biella runtime credentials must be root-owned 0600' >&2; exit 1; }
set -a
# shellcheck disable=SC1090
source "$RUNTIME_ENV"
set +a
[[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ]] || { echo 'Cloudflare account ID is required' >&2; exit 1; }
TUNNEL_API_TOKEN="${CLOUDFLARE_TUNNEL_API_TOKEN:-${CLOUDFLARE_API_TOKEN:-}}"
[[ -n "$TUNNEL_API_TOKEN" ]] || { echo 'Cloudflare Tunnel/DNS API token is required' >&2; exit 1; }
command -v cloudflared >/dev/null 2>&1 || { echo 'cloudflared is required' >&2; exit 1; }

install -d -o root -g root -m 700 "$CONFIG_DIR"
curl_cfg="$(mktemp "$CONFIG_DIR/control-api.XXXXXX")"
work_dir="$(mktemp -d /tmp/biella-control-cloudflare.XXXXXX)"
trap 'rm -f -- "$curl_cfg"; rm -rf -- "$work_dir"' EXIT
chmod 600 "$curl_cfg"
printf 'header = "Authorization: Bearer %s"\n' "$TUNNEL_API_TOKEN" > "$curl_cfg"
unset TUNNEL_API_TOKEN

cf_get() {
  local path="$1" output="$2" code
  code="$(curl -sS -o "$output" -w '%{http_code}' --config "$curl_cfg" "$API$path" || true)"
  [[ "$code" == 2* ]] || { echo "Cloudflare GET failed HTTP=$code path=$path" >&2; return 1; }
}

cf_write() {
  local method="$1" path="$2" body="$3" output="$4" code
  code="$(curl -sS -o "$output" -w '%{http_code}' --config "$curl_cfg" -H 'Content-Type: application/json' -X "$method" --data-binary "@$body" "$API$path" || true)"
  [[ "$code" == 2* ]] || {
    python3 - "$output" <<'PY' >&2 || true
import json,sys
try:
    d=json.load(open(sys.argv[1]))
    print('Cloudflare errors:', [(x.get('code'),x.get('message')) for x in d.get('errors',[])])
except Exception:
    pass
PY
    echo "Cloudflare $method failed HTTP=$code path=$path" >&2
    return 1
  }
}

zone_json="$work_dir/zones.json"
cf_get "/zones?name=biellagames.dev" "$zone_json"
zone_id="$(python3 - "$zone_json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); r=d.get('result',[])
if len(r)!=1: raise SystemExit('expected exactly one biellagames.dev zone')
print(r[0]['id'])
PY
)"

tunnels_json="$work_dir/tunnels.json"
cf_get "/accounts/${CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel?is_deleted=false" "$tunnels_json"
tunnel_id="$(python3 - "$tunnels_json" "$TUNNEL_NAME" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); name=sys.argv[2]
r=[x for x in d.get('result',[]) if x.get('name')==name]
if len(r)>1: raise SystemExit('multiple tunnels share the Biella control name')
print(r[0]['id'] if r else '')
PY
)"

if [[ -z "$tunnel_id" ]]; then
  tunnel_secret="$(python3 - <<'PY'
import base64,secrets
print(base64.b64encode(secrets.token_bytes(32)).decode())
PY
)"
  create_body="$work_dir/create-tunnel.json"
  printf '{"name":"%s","tunnel_secret":"%s","config_src":"local"}\n' "$TUNNEL_NAME" "$tunnel_secret" > "$create_body"
  chmod 600 "$create_body"
  create_json="$work_dir/create-tunnel-response.json"
  cf_write POST "/accounts/${CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel" "$create_body" "$create_json"
  tunnel_id="$(python3 - "$create_json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); print(d['result']['id'])
PY
)"
  credentials_file="$CONFIG_DIR/${tunnel_id}.json"
  printf '{"AccountTag":"%s","TunnelSecret":"%s","TunnelID":"%s"}\n' "$CLOUDFLARE_ACCOUNT_ID" "$tunnel_secret" "$tunnel_id" > "$credentials_file"
  chmod 600 "$credentials_file"
  chown root:root "$credentials_file"
  unset tunnel_secret
else
  credentials_file="$CONFIG_DIR/${tunnel_id}.json"
  [[ -f "$credentials_file" ]] || { echo 'existing Biella control tunnel has no local credentials; refusing replacement' >&2; exit 1; }
fi

config_tmp="$(mktemp "$CONFIG_DIR/biella-control.yml.XXXXXX")"
cat > "$config_tmp" <<EOF
tunnel: $tunnel_id
credentials-file: $credentials_file
ingress:
  - hostname: $HOSTNAME
    service: $ORIGIN
  - service: http_status:404
EOF
chmod 600 "$config_tmp"
chown root:root "$config_tmp"
mv -f -- "$config_tmp" "$CONFIG_FILE"

target="${tunnel_id}.cfargotunnel.com"
dns_json="$work_dir/dns.json"
cf_get "/zones/${zone_id}/dns_records?name=${HOSTNAME}" "$dns_json"
dns_state="$(python3 - "$dns_json" "$target" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); target=sys.argv[2]
r=d.get('result',[])
if not r:
    print('NONE')
elif len(r)==1 and r[0].get('type')=='CNAME' and r[0].get('content')==target:
    print('OK:'+r[0]['id']+':'+str(bool(r[0].get('proxied'))).lower())
else:
    print('CONFLICT')
PY
)"

if [[ "$dns_state" == CONFLICT ]]; then
  echo 'conflicting DNS record exists for control.biellagames.dev; refusing overwrite' >&2
  exit 1
elif [[ "$dns_state" == NONE ]]; then
  dns_body="$work_dir/dns-create.json"
  printf '{"type":"CNAME","name":"%s","content":"%s","proxied":true,"ttl":1}\n' "$HOSTNAME" "$target" > "$dns_body"
  cf_write POST "/zones/${zone_id}/dns_records" "$dns_body" "$work_dir/dns-create-response.json"
elif [[ "$dns_state" == OK:*:false ]]; then
  dns_record_id="${dns_state#OK:}"
  dns_record_id="${dns_record_id%:false}"
  dns_body="$work_dir/dns-update.json"
  printf '{"proxied":true}\n' > "$dns_body"
  cf_write PATCH "/zones/${zone_id}/dns_records/${dns_record_id}" "$dns_body" "$work_dir/dns-update-response.json"
fi

install -o root -g root -m 644 "$SERVICE_SOURCE" /etc/systemd/system/biella-control-tunnel.service
systemctl daemon-reload
systemctl enable --now biella-control-tunnel.service >/dev/null

for attempt in $(seq 1 30); do
  if curl -fsS --max-time 10 "https://${HOSTNAME}/v1/control/session" > "$work_dir/readback.json" 2>/dev/null; then
    echo "Biella control tunnel connected: https://${HOSTNAME}/control/"
    exit 0
  fi
  sleep 2
done

echo 'Cloudflare tunnel started but external control readback did not become ready' >&2
exit 1
