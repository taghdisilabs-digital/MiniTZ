#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly INSTALL_DIR="${MINITZ_AI_INSTALL_DIR:-/usr/local/lib/minitz-ai}"
readonly CODEX_LINK="/usr/local/bin/minitz-codex"
readonly PROJECT_CELL_LINK="/usr/local/bin/minitz-project-cell"
readonly OWNER_SLEEP_LINK="/usr/local/bin/minitz-owner-sleep"
readonly OWNER_ON_LINK="/usr/local/bin/minitz-owner-on"
readonly OWNER_OFF_LINK="/usr/local/bin/minitz-owner-off"
readonly MANAGED_PREFIX="$INSTALL_DIR/"
readonly LEGACY_MANAGED_PREFIX="/usr/local/lib/biella-ai/"
readonly PRODUCTION_UNIT=/etc/systemd/system/minitz-production.service

[[ "$EUID" -eq 0 ]] || { printf 'Run the MiniTZ AI installer as root.\n' >&2; exit 1; }

retire_legacy_runtime_units() {
  local unit
  for unit in \
    biella-codex-production.service \
    biella-control-gateway.service \
    biella-control-tunnel.service \
    biella-qwen-residency.service \
    biella-ollama.service \
    minitz-local-ai-ready.service; do
    systemctl stop "$unit" >/dev/null 2>&1 || true
    systemctl disable "$unit" >/dev/null 2>&1 || true
  done
  rm -f -- \
    /etc/systemd/system/biella-codex-production.service \
    /etc/systemd/system/biella-control-gateway.service \
    /etc/systemd/system/biella-control-tunnel.service \
    /etc/systemd/system/biella-qwen-residency.service \
    /etc/systemd/system/biella-ollama.service \
    /etc/systemd/system/minitz-local-ai-ready.service \
    /etc/systemd/system/minitz-on.target.d/10-reboot-readiness.conf
  rm -rf -- \
    /etc/systemd/system/biella-codex-production.service.d \
    /etc/systemd/system/biella-ollama.service.d
}

retire_legacy_runtime_units

python3 "$SOURCE_DIR/minitz_execution_style.py" audit \
  --runner "$SOURCE_DIR/minitz_production_runner.py" \
  --unit "$SOURCE_DIR/minitz-production.service" \
  --installer "$SOURCE_DIR/install-minitz-ai.sh"

remove_managed_link() {
  local path="$1"
  if [[ -L "$path" ]]; then
    local target
    target="$(readlink "$path")"
    if [[ "$target" == "$MANAGED_PREFIX"* || "$target" == "$LEGACY_MANAGED_PREFIX"* ]]; then
      rm -f -- "$path"
    fi
  fi
}

install -d -o root -g root -m 755 "$INSTALL_DIR"
install -o root -g root -m 755 "$SOURCE_DIR/../project-cell/minitz-project-cell" "$INSTALL_DIR/minitz-project-cell"
install -o root -g root -m 755 \
  "$SOURCE_DIR/minitz-ai-start.sh" \
  "$SOURCE_DIR/minitz-saturn-mcp.sh" \
  "$SOURCE_DIR/minitz-saturn-probe.py" \
  "$SOURCE_DIR/minitz-codex.sh" \
  "$SOURCE_DIR/minitz-source-sync.sh" \
  "$SOURCE_DIR/minitz-codex-router" \
  "$SOURCE_DIR/minitz-codex-account" \
  "$SOURCE_DIR/minitz-owner-sleep" \
  "$SOURCE_DIR/minitz-owner-on" \
  "$SOURCE_DIR/minitz-owner-off" \
  "$SOURCE_DIR/minitz_lifecycle.py" \
  "$SOURCE_DIR/minitz_production_runner.py" \
  "$INSTALL_DIR/"
install -o root -g root -m 644 \
  "$SOURCE_DIR/minitz_production_state.py" \
  "$SOURCE_DIR/minitz_production_events.py" \
  "$SOURCE_DIR/minitz_memory_compactor.py" \
  "$SOURCE_DIR/minitz_data_residency.py" \
  "$SOURCE_DIR/minitz_codex_account_pool.py" \
  "$SOURCE_DIR/minitz_private_secret_verifier.py" \
  "$SOURCE_DIR/minitz_main_coder.py" \
  "$SOURCE_DIR/minitz_commander_fabric.py" \
  "$SOURCE_DIR/minitz_boost_fabric.py" \
  "$SOURCE_DIR/minitz_founder_extension.py" \
  "$SOURCE_DIR/minitz_taskbooster.py" \
  "$SOURCE_DIR/minitz_task_program.py" \
  "$SOURCE_DIR/minitz_task_guidance.py" \
  "$SOURCE_DIR/minitz_policy.py" \
  "$SOURCE_DIR/minitz_task_packet.py" \
  "$SOURCE_DIR/minitz_task_ids.py" \
  "$SOURCE_DIR/minitz_task_ledger.py" \
  "$SOURCE_DIR/minitz_execution_map.py" \
  "$SOURCE_DIR/minitz_publication.py" \
  "$SOURCE_DIR/minitz_codex_routing.py" \
  "$SOURCE_DIR/minitz_execution_style.py" \
  "$SOURCE_DIR/minitz_production_evidence.py" \
  "$SOURCE_DIR/minitz_completion_truth.py" \
  "$INSTALL_DIR/"
install -o root -g root -m 755 "$SOURCE_DIR/minitz-codex-router" /usr/local/bin/minitz-codex-router
install -o root -g root -m 755 "$SOURCE_DIR/minitz-codex-account" /usr/local/bin/minitz-codex-account
install -o root -g root -m 644 "$SOURCE_DIR/minitz-production.service" "$PRODUCTION_UNIT"
install -o root -g root -m 644 "$SOURCE_DIR/minitz-on.target" /etc/systemd/system/minitz-on.target
systemctl daemon-reload

for managed_link in "$CODEX_LINK" "$PROJECT_CELL_LINK" "$OWNER_SLEEP_LINK" "$OWNER_ON_LINK" "$OWNER_OFF_LINK"; do
  remove_managed_link "$managed_link"
done

if [[ -e "$CODEX_LINK" || -L "$CODEX_LINK" ]]; then
  [[ -L "$CODEX_LINK" && "$(readlink "$CODEX_LINK")" == "$INSTALL_DIR/minitz-codex.sh" ]] || {
    printf 'Refusing to replace unrelated path: %s\n' "$CODEX_LINK" >&2
    exit 1
  }
else
  ln -s "$INSTALL_DIR/minitz-codex.sh" "$CODEX_LINK"
fi

if [[ -e "$OWNER_SLEEP_LINK" || -L "$OWNER_SLEEP_LINK" ]]; then
  [[ -L "$OWNER_SLEEP_LINK" && "$(readlink "$OWNER_SLEEP_LINK")" == "$INSTALL_DIR/minitz-owner-sleep" ]] || {
    printf 'Refusing to replace unrelated path: %s\n' "$OWNER_SLEEP_LINK" >&2
    exit 1
  }
else
  ln -s "$INSTALL_DIR/minitz-owner-sleep" "$OWNER_SLEEP_LINK"
fi

for pair in "$OWNER_ON_LINK:$INSTALL_DIR/minitz-owner-on" "$OWNER_OFF_LINK:$INSTALL_DIR/minitz-owner-off"; do
  path="${pair%%:*}"
  target="${pair#*:}"
  if [[ -e "$path" || -L "$path" ]]; then
    [[ -L "$path" && "$(readlink "$path")" == "$target" ]] || {
      printf 'Refusing to replace unrelated path: %s\n' "$path" >&2
      exit 1
    }
  else
    ln -s "$target" "$path"
  fi
done

if [[ -e "$PROJECT_CELL_LINK" || -L "$PROJECT_CELL_LINK" ]]; then
  [[ -L "$PROJECT_CELL_LINK" && "$(readlink "$PROJECT_CELL_LINK")" == "$INSTALL_DIR/minitz-project-cell" ]] || {
    printf 'Refusing to replace unrelated path: %s\n' "$PROJECT_CELL_LINK" >&2
    exit 1
  }
else
  ln -s "$INSTALL_DIR/minitz-project-cell" "$PROJECT_CELL_LINK"
fi

printf 'Installed unified MiniTZ Codex controller under %s.\n' "$INSTALL_DIR"
printf 'Only AI/production entrypoint: minitz-codex\n'
