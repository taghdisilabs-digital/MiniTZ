#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly INSTALL_DIR="${BIELLA_WORKSTATION_INSTALL_DIR:-/usr/local/lib/biella-workstation}"
readonly CLI_LINK="/usr/local/bin/biella"
readonly PROVIDER_CONFIG_LINK="/usr/local/bin/biella-provider-configure"
readonly PROVIDER_CHECK_LINK="/usr/local/bin/biella-provider-check"

[[ "$EUID" -eq 0 ]] || { printf 'Run workstation installer as root.\n' >&2; exit 1; }

install -d -o root -g root -m 755 "$INSTALL_DIR"
install -o root -g root -m 755 \
  "$SOURCE_DIR/biella" \
  "$SOURCE_DIR/biella-lib.sh" \
  "$SOURCE_DIR/biella-provider-check.sh" \
  "$SOURCE_DIR/biella-provider-configure.sh" \
  "$INSTALL_DIR/"
install -d -o root -g root -m 700 /root/.codex
install -o root -g root -m 644 "$SOURCE_DIR/AGENTS.md" /root/.codex/AGENTS.md
install -o root -g root -m 644 "$SOURCE_DIR/biella-ollama.service" /etc/systemd/system/biella-ollama.service
if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload
  systemctl enable biella-ollama.service >/dev/null
fi
ensure_link() {
  local link_path="$1" new_target="$2" old_target="${3:-}"
  if [[ -e "$link_path" || -L "$link_path" ]]; then
    [[ -L "$link_path" ]] || { printf 'Refusing to replace unrelated path: %s\n' "$link_path" >&2; exit 1; }
    current_target="$(readlink "$link_path")"
    [[ "$current_target" == "$new_target" || ( -n "$old_target" && "$current_target" == "$old_target" ) ]] || {
      printf 'Refusing to replace unrelated path: %s\n' "$link_path" >&2
      exit 1
    }
    ln -sfn "$new_target" "$link_path"
  else
    ln -s "$new_target" "$link_path"
  fi
}

ensure_link "$CLI_LINK" "$INSTALL_DIR/biella"
ensure_link "$PROVIDER_CONFIG_LINK" "$INSTALL_DIR/biella-provider-configure.sh" /root/biella/provider-configure.sh
ensure_link "$PROVIDER_CHECK_LINK" "$INSTALL_DIR/biella-provider-check.sh" /root/biella/provider-check.sh

install -d -o root -g root -m 755 /mnt/biella-extra/biella-runtime
for name in cache tmp logs builds models; do
  install -d -o root -g root -m 755 "/mnt/biella-extra/biella-runtime/$name"
done

printf 'Installed Biella workstation supervisor.\n'
printf 'Run: biella status\n'
