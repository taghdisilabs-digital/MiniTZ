#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly INSTALL_DIR="${BIELLA_WORKSTATION_INSTALL_DIR:-/usr/local/lib/biella-workstation}"
readonly CLI_LINK="/usr/local/bin/biella"
readonly CONFIG_LINK="/usr/local/bin/biella-provider-configure"
readonly CHECK_LINK="/usr/local/bin/biella-provider-check"

[[ "$EUID" -eq 0 ]] || { printf 'Run workstation installer as root.\n' >&2; exit 1; }

ensure_link() {
  local link_path="$1" target="$2" legacy="${3:-}"
  if [[ -e "$link_path" || -L "$link_path" ]]; then
    if [[ -L "$link_path" && "$(readlink "$link_path")" == "$target" ]]; then
      return 0
    fi
    if [[ -n "$legacy" && -L "$link_path" && "$(readlink "$link_path")" == "$legacy" ]]; then
      rm -f -- "$link_path"
    else
      printf 'Refusing to replace unrelated path: %s\n' "$link_path" >&2
      return 1
    fi
  fi
  ln -s "$target" "$link_path"
}

install -d -o root -g root -m 755 "$INSTALL_DIR"
install -o root -g root -m 755 \
  "$SOURCE_DIR/biella" \
  "$SOURCE_DIR/biella-lib.sh" \
  "$SOURCE_DIR/biella-provider-configure.sh" \
  "$SOURCE_DIR/biella-provider-check.sh" \
  "$SOURCE_DIR/biella-resource.py" \
  "$SOURCE_DIR/provider-registry.json" \
  "$INSTALL_DIR/"

install -d -o root -g root -m 700 /root/.codex
install -o root -g root -m 644 "$SOURCE_DIR/AGENTS.md" /root/.codex/AGENTS.md
install -o root -g root -m 644 "$SOURCE_DIR/biella-ollama.service" /etc/systemd/system/biella-ollama.service

if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload
  systemctl enable biella-ollama.service >/dev/null
fi

ensure_link "$CLI_LINK" "$INSTALL_DIR/biella"
ensure_link "$CONFIG_LINK" "$INSTALL_DIR/biella-provider-configure.sh" /root/biella/provider-configure.sh
ensure_link "$CHECK_LINK" "$INSTALL_DIR/biella-provider-check.sh" /root/biella/provider-check.sh

install -d -o root -g root -m 755 /mnt/biella-extra/biella-runtime
for name in cache tmp logs builds models; do
  install -d -o root -g root -m 755 "/mnt/biella-extra/biella-runtime/$name"
done

printf 'Installed Biella workstation supervisor.\n'
printf 'Run: biella status\n'
