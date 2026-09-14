#!/usr/bin/env bash
set -Eeuo pipefail
readonly SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly INSTALL_DIR="${MINITZ_WORKSTATION_INSTALL_DIR:-/usr/local/lib/minitz-workstation}"
readonly CLI_LINK="${MINITZ_WORKSTATION_CLI_LINK:-/usr/local/bin/minitz-workstation}"
readonly RESOURCE_LINK="${MINITZ_RESOURCE_CLI_LINK:-/usr/local/bin/minitz-resource}"
[[ "$EUID" -eq 0 ]] || { printf 'Run MiniTZ workstation installer as root.\n' >&2; exit 1; }
install -d -o root -g root -m 755 "$INSTALL_DIR"
install -o root -g root -m 755 "$SOURCE_DIR/minitz-workstation" "$SOURCE_DIR/minitz-lib.sh" "$SOURCE_DIR/minitz-provider-configure.sh" "$SOURCE_DIR/minitz-provider-check.sh" "$SOURCE_DIR/minitz-resource.py" "$SOURCE_DIR/minitz-qwen-ready.sh" "$SOURCE_DIR/minitz-qwen-residency.sh" "$INSTALL_DIR/"
install -o root -g root -m 644 "$SOURCE_DIR/minitz-gpu-residency.json" "$SOURCE_DIR/provider-registry.json" "$INSTALL_DIR/"
if [[ -e "$CLI_LINK" || -L "$CLI_LINK" ]]; then
  [[ -L "$CLI_LINK" && "$(readlink "$CLI_LINK")" == "$INSTALL_DIR/minitz-workstation" ]] || { printf 'Refusing to replace unrelated path: %s\n' "$CLI_LINK" >&2; exit 1; }
else
  ln -s "$INSTALL_DIR/minitz-workstation" "$CLI_LINK"
fi
if [[ -e "$RESOURCE_LINK" || -L "$RESOURCE_LINK" ]]; then
  [[ -L "$RESOURCE_LINK" && "$(readlink "$RESOURCE_LINK")" == "$INSTALL_DIR/minitz-resource.py" ]] || { printf 'Refusing to replace unrelated path: %s\n' "$RESOURCE_LINK" >&2; exit 1; }
else
  ln -s "$INSTALL_DIR/minitz-resource.py" "$RESOURCE_LINK"
fi
printf 'Installed MiniTZ workstation resource client.\nRun: minitz-workstation status\n'
