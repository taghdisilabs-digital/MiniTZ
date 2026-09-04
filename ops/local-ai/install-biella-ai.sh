#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly INSTALL_DIR="${BIELLA_AI_INSTALL_DIR:-/usr/local/lib/biella-ai}"
readonly START_LINK="/usr/local/bin/biella-ai-start"
readonly CODEX_LINK="/usr/local/bin/biella-codex"
readonly LOCAL_AGENT_LINK="/usr/local/bin/biella-local-agent"

[[ "$EUID" -eq 0 ]] || {
  printf 'Run the Biella local-AI installer as root.\n' >&2
  exit 1
}

install -d -o root -g root -m 755 "$INSTALL_DIR"
install -o root -g root -m 755 \
  "$SOURCE_DIR/biella-ai-start.sh" \
  "$SOURCE_DIR/biella-saturn-mcp.sh" \
  "$SOURCE_DIR/biella-saturn-probe.py" \
  "$SOURCE_DIR/biella-codex.sh" \
  "$SOURCE_DIR/biella-local-agent.sh" \
  "$SOURCE_DIR/qwen-codex-model-catalog.json" \
  "$INSTALL_DIR/"

for link_pair in \
  "$START_LINK:$INSTALL_DIR/biella-ai-start.sh" \
  "$CODEX_LINK:$INSTALL_DIR/biella-codex.sh" \
  "$LOCAL_AGENT_LINK:$INSTALL_DIR/biella-local-agent.sh"; do
  link_path="${link_pair%%:*}"
  link_target="${link_pair#*:}"
  if [[ -e "$link_path" || -L "$link_path" ]]; then
    [[ -L "$link_path" && "$(readlink "$link_path")" == "$link_target" ]] || {
      printf 'Refusing to replace an unrelated path: %s\n' "$link_path" >&2
      exit 1
    }
  else
    ln -s "$link_target" "$link_path"
  fi
done

printf 'Installed Biella local-AI runtime under %s.\n' "$INSTALL_DIR"
printf 'Start with: biella-ai-start\n'
printf 'Run Codex with: biella-codex\n'
printf 'Run fast local agent with: biella-local-agent\n'
