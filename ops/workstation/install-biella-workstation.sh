#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly INSTALL_DIR="${BIELLA_WORKSTATION_INSTALL_DIR:-/usr/local/lib/biella-workstation}"
readonly CLI_LINK="/usr/local/bin/biella"

[[ "$EUID" -eq 0 ]] || { printf 'Run workstation installer as root.\n' >&2; exit 1; }

install -d -o root -g root -m 755 "$INSTALL_DIR"
install -o root -g root -m 755 "$SOURCE_DIR/biella" "$SOURCE_DIR/biella-lib.sh" "$INSTALL_DIR/"

if [[ -e "$CLI_LINK" || -L "$CLI_LINK" ]]; then
  [[ -L "$CLI_LINK" && "$(readlink "$CLI_LINK")" == "$INSTALL_DIR/biella" ]] || {
    printf 'Refusing to replace unrelated path: %s\n' "$CLI_LINK" >&2
    exit 1
  }
else
  ln -s "$INSTALL_DIR/biella" "$CLI_LINK"
fi

install -d -o root -g root -m 755 /mnt/biella-extra/biella-runtime
for name in cache tmp logs builds models; do
  install -d -o root -g root -m 755 "/mnt/biella-extra/biella-runtime/$name"
done

printf 'Installed Biella workstation supervisor.\n'
printf 'Run: biella status\n'
