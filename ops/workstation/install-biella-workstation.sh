#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly INSTALL_DIR="${BIELLA_WORKSTATION_INSTALL_DIR:-/usr/local/lib/biella-workstation}"
readonly CLI_LINK="/usr/local/bin/biella"
readonly CONFIG_LINK="/usr/local/bin/biella-provider-configure"
readonly CHECK_LINK="/usr/local/bin/biella-provider-check"
readonly BROWSER_CLOUD_LINK="/usr/local/bin/minitz-browser-cloud"

ollama_enablement="$(systemctl is-enabled biella-ollama.service 2>/dev/null || true)"
qwen_enablement="$(systemctl is-enabled biella-qwen-residency.service 2>/dev/null || true)"
ollama_active="$(systemctl is-active biella-ollama.service 2>/dev/null || true)"
qwen_active="$(systemctl is-active biella-qwen-residency.service 2>/dev/null || true)"

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
  "$SOURCE_DIR/minitz-browser-cloud.py" \
  "$SOURCE_DIR/install-package-tools.sh" \
  "$SOURCE_DIR/INSTALLERS.md" \
  "$SOURCE_DIR/biella-qwen-ready.sh" \
  "$SOURCE_DIR/biella-qwen-residency.sh" \
  "$SOURCE_DIR/provider-registry.json" \
  "$SOURCE_DIR/setup-unreal-win64.ps1" \
  "$SOURCE_DIR/build-unreal-win64.ps1" \
  "$SOURCE_DIR/UNREAL_WIN64.md" \
  "$INSTALL_DIR/"
install -o root -g root -m 644 \
  "$SOURCE_DIR/windows-browser-cloud-targets.json" \
  "$SOURCE_DIR/WINDOWS_BROWSER_CLOUD.md" \
  "$INSTALL_DIR/"

install -d -o root -g root -m 700 /root/.codex
install -o root -g root -m 644 "$SOURCE_DIR/AGENTS.md" /root/.codex/AGENTS.md
install -o root -g root -m 644 "$SOURCE_DIR/biella-ollama.service" /etc/systemd/system/biella-ollama.service
install -o root -g root -m 644 "$SOURCE_DIR/biella-qwen-residency.service" /etc/systemd/system/biella-qwen-residency.service

if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload
  if [[ "$ollama_enablement" == "enabled" ]]; then
    systemctl enable biella-ollama.service >/dev/null
  else
    systemctl disable biella-ollama.service >/dev/null
  fi
  if [[ "$qwen_enablement" == "enabled" ]]; then
    systemctl enable biella-qwen-residency.service >/dev/null
  else
    systemctl disable biella-qwen-residency.service >/dev/null
  fi
  # Installation must not turn an already-running optional resource into downtime.
  # Restore only pre-existing active state; never start a previously inactive service.
  if [[ "$ollama_active" == "active" ]]; then
    systemctl start biella-ollama.service
  fi
  if [[ "$qwen_active" == "active" ]]; then
    systemctl start biella-qwen-residency.service
  fi
fi

ensure_link "$CLI_LINK" "$INSTALL_DIR/biella"
ensure_link "$CONFIG_LINK" "$INSTALL_DIR/biella-provider-configure.sh" /root/biella/provider-configure.sh
ensure_link "$CHECK_LINK" "$INSTALL_DIR/biella-provider-check.sh" /root/biella/provider-check.sh
ensure_link "$BROWSER_CLOUD_LINK" "$INSTALL_DIR/minitz-browser-cloud.py"

install -d -o root -g root -m 755 /mnt/biella-extra/biella-runtime
for name in cache tmp logs builds models; do
  install -d -o root -g root -m 755 "/mnt/biella-extra/biella-runtime/$name"
done

printf 'Installed Biella workstation supervisor.\n'
printf 'Run: biella status\n'
