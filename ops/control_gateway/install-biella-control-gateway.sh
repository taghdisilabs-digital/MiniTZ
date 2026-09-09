#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly INSTALL_DIR="${BIELLA_CONTROL_INSTALL_DIR:-/usr/local/lib/biella-control}"
readonly SITE_ROOT="${BIELLA_CONTROL_SITE_ROOT:-/var/lib/biella-control/site}"
readonly STATE_DIR="$(dirname "$SITE_ROOT")"
site_source="${BIELLA_CONTROL_SITE_SOURCE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site-dir) site_source="${2:?missing --site-dir value}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ "$EUID" -eq 0 ]] || { echo 'run control gateway installer as root' >&2; exit 1; }
install -d -o root -g root -m 755 "$INSTALL_DIR" "$STATE_DIR"
install -d -o root -g root -m 700 /root/.config/biella-control
install -o root -g root -m 644 \
  "$SOURCE_DIR/biella_control_gateway.py" \
  "$SOURCE_DIR/biella_live_projection.py" \
  "$SOURCE_DIR/minitz_live_projection.py" \
  "$SOURCE_DIR/biella_control_assets.py" \
  "$SOURCE_DIR/biella_control_state.py" \
  "$SOURCE_DIR/biella_control_runner.py" \
  "$SOURCE_DIR/biella_control_main.py" \
  "$INSTALL_DIR/"
install -o root -g root -m 600 "$SOURCE_DIR/biella_control_auth.py" "$INSTALL_DIR/"
install -o root -g root -m 755 "$SOURCE_DIR/biella-control-auth" /usr/local/bin/biella-control-auth
install -o root -g root -m 755 "$SOURCE_DIR/biella-control-cloudflare-token" /usr/local/bin/biella-control-cloudflare-token
install -o root -g root -m 755 "$SOURCE_DIR/configure-biella-control-tunnel.sh" /usr/local/bin/biella-control-tunnel-configure
install -o root -g root -m 644 "$SOURCE_DIR/biella-control-tunnel.service" "$INSTALL_DIR/biella-control-tunnel.service"

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
install -o root -g root -m 644 "$SOURCE_DIR/biella-control-gateway.service" /etc/systemd/system/biella-control-gateway.service
systemctl daemon-reload
systemctl enable biella-control-gateway.service >/dev/null
systemctl restart biella-control-gateway.service

echo 'Installed Biella control gateway.'
echo 'Local URL: http://127.0.0.1:8787/control/'
echo 'Configure passwords with: biella-control-auth configure'
