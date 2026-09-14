#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly INSTALL_DIR="${MINITZ_CONTROL_INSTALL_DIR:-/usr/local/lib/minitz-control}"
readonly SITE_ROOT="${MINITZ_CONTROL_SITE_ROOT:-/root/attached-storage/minitz-os-sandbox/state/control/site}"
readonly STATE_DIR="$(dirname "$SITE_ROOT")"
site_source="${MINITZ_CONTROL_SITE_SOURCE:-}"
control_unit_existed=0
[[ -e /etc/systemd/system/minitz-control-gateway.service || -L /etc/systemd/system/minitz-control-gateway.service ]] && control_unit_existed=1
control_enablement="$(systemctl is-enabled minitz-control-gateway.service 2>/dev/null || true)"
control_active="$(systemctl is-active minitz-control-gateway.service 2>/dev/null || true)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site-dir) site_source="${2:?missing --site-dir value}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ "$EUID" -eq 0 ]] || { echo 'run control gateway installer as root' >&2; exit 1; }
install -d -o root -g root -m 755 "$INSTALL_DIR" "$STATE_DIR"
install -d -o root -g root -m 700 /root/attached-storage/minitz-os-sandbox/state/credentials/control
install -o root -g root -m 644 \
  "$SOURCE_DIR/minitz_control_gateway.py" \
  "$SOURCE_DIR/minitz_base_projection.py" \
  "$SOURCE_DIR/minitz_live_projection.py" \
  "$SOURCE_DIR/minitz_control_assets.py" \
  "$SOURCE_DIR/minitz_control_state.py" \
  "$SOURCE_DIR/minitz_control_runner.py" \
  "$SOURCE_DIR/minitz_control_main.py" \
  "$INSTALL_DIR/"
install -o root -g root -m 600 "$SOURCE_DIR/minitz_control_auth.py" "$INSTALL_DIR/"
install -o root -g root -m 755 "$SOURCE_DIR/minitz-control-auth" /usr/local/bin/minitz-control-auth
install -o root -g root -m 755 "$SOURCE_DIR/minitz-control-cloudflare-token" /usr/local/bin/minitz-control-cloudflare-token
install -o root -g root -m 755 "$SOURCE_DIR/configure-minitz-control-tunnel.sh" /usr/local/bin/minitz-control-tunnel-configure
install -o root -g root -m 644 "$SOURCE_DIR/minitz-control-tunnel.service" "$INSTALL_DIR/minitz-control-tunnel.service"

if [[ -n "$site_source" ]]; then
  [[ -f "$site_source/control/index.html" ]] || { echo 'site build missing control/index.html' >&2; exit 1; }
  [[ -f "$site_source/data/control-runtime.json" ]] || { echo 'site build missing data/control-runtime.json' >&2; exit 1; }
  stage="$(mktemp -d "$STATE_DIR/site.stage.XXXXXX")"
  cp -a "$site_source/." "$stage/"
  chown -R root:root "$stage"
  find "$stage" -type d -exec chmod 755 {} +
  find "$stage" -type f -exec chmod 644 {} +
  old="$STATE_DIR/site.previous"
  rm -rf -- "$old"
  if [[ -d "$SITE_ROOT" ]]; then mv "$SITE_ROOT" "$old"; fi
  mv "$stage" "$SITE_ROOT"
  rm -rf -- "$old"
fi

[[ -f "$SITE_ROOT/control/index.html" ]] || { echo 'no installed control site; provide --site-dir' >&2; exit 1; }
install -o root -g root -m 644 "$SOURCE_DIR/minitz-control-gateway.service" /etc/systemd/system/minitz-control-gateway.service
systemctl daemon-reload
if [[ "$control_unit_existed" -eq 0 ]]; then
  systemctl enable minitz-control-gateway.service >/dev/null
elif [[ "$control_enablement" == "enabled" ]]; then
  systemctl enable minitz-control-gateway.service >/dev/null
else
  systemctl disable minitz-control-gateway.service >/dev/null
fi
if [[ "$control_active" == "active" ]]; then
  systemctl restart minitz-control-gateway.service
fi

echo 'Installed MiniTZ control gateway.'
echo 'Local URL: http://127.0.0.1:8787/control/'
echo 'Configure passwords with: minitz-control-auth configure'
