#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly INSTALL_DIR="${BIELLA_AI_INSTALL_DIR:-/usr/local/lib/biella-ai}"
readonly CODEX_LINK="/usr/local/bin/biella-codex"
readonly MANAGED_PREFIX="$INSTALL_DIR/"

[[ "$EUID" -eq 0 ]] || { printf 'Run the Biella AI installer as root.\n' >&2; exit 1; }

remove_managed_link() {
  local path="$1"
  if [[ -L "$path" ]]; then
    local target
    target="$(readlink "$path")"
    [[ "$target" == "$MANAGED_PREFIX"* ]] && rm -f -- "$path"
  fi
}

install -d -o root -g root -m 755 "$INSTALL_DIR"
install -o root -g root -m 755 \
  "$SOURCE_DIR/biella-ai-start.sh" \
  "$SOURCE_DIR/biella-saturn-mcp.sh" \
  "$SOURCE_DIR/biella-saturn-probe.py" \
  "$SOURCE_DIR/biella-codex.sh" \
  "$SOURCE_DIR/biella_production_runner.py" \
  "$INSTALL_DIR/"
install -o root -g root -m 644 \
  "$SOURCE_DIR/biella_production_state.py" \
  "$SOURCE_DIR/biella_task_packet.py" \
  "$SOURCE_DIR/biella_codex_routing.py" \
  "$SOURCE_DIR/biella_production_evidence.py" \
  "$INSTALL_DIR/"
for obsolete in \
  /usr/local/bin/biella-ai-start \
  /usr/local/bin/biella-local-agent \
  /usr/local/bin/biella-work \
  /usr/local/bin/biella-model \
  /usr/local/bin/biella-luna \
  /usr/local/bin/biella-astra; do
  remove_managed_link "$obsolete"
done

if [[ -e "$CODEX_LINK" || -L "$CODEX_LINK" ]]; then
  [[ -L "$CODEX_LINK" && "$(readlink "$CODEX_LINK")" == "$INSTALL_DIR/biella-codex.sh" ]] || {
    printf 'Refusing to replace unrelated path: %s\n' "$CODEX_LINK" >&2
    exit 1
  }
else
  ln -s "$INSTALL_DIR/biella-codex.sh" "$CODEX_LINK"
fi

rm -f -- \
  "$INSTALL_DIR/biella-local-agent.sh" \
  "$INSTALL_DIR/biella-work.sh" \
  "$INSTALL_DIR/biella-model.sh" \
  "$INSTALL_DIR/biella-luna.sh" \
  "$INSTALL_DIR/biella-astra.sh" \
  "$INSTALL_DIR/biella-work-contract.md" \
  "$INSTALL_DIR/biella_codex_feeder.py"

printf 'Installed unified Biella Codex controller under %s.\n' "$INSTALL_DIR"
printf 'Only AI/production entrypoint: biella-codex\n'
