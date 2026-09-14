#!/usr/bin/env bash
set -Eeuo pipefail
ENV_FILE=/etc/minitz/qwen-residency.env
MODE="${1:-status}"
current_mode() {
  if [[ -f "$ENV_FILE" ]]; then
    sed -n 's/^MINITZ_QWEN_NUM_GPU=//p' "$ENV_FILE" | tail -n 1
  fi
}
running_mode() {
  ps -eo args= | awk '/[l]lama-server/ {for(i=1;i<=NF;i++) if($i=="-ngl" && i<NF){print $(i+1); exit}}'
}
case "$MODE" in
  38)
    [[ "$EUID" -eq 0 ]] || { echo "run as root" >&2; exit 1; }
    install -d -o root -g root -m 755 /etc/minitz
    tmp="$(mktemp /etc/minitz/qwen-residency.env.XXXXXX)"
    printf 'MINITZ_QWEN_NUM_GPU=%s\nMINITZ_QWEN_NUM_CTX=16384\n' "$MODE" > "$tmp"
    chown root:root "$tmp"; chmod 644 "$tmp"; mv -f "$tmp" "$ENV_FILE"
    systemctl daemon-reload
    systemctl restart minitz-qwen-residency.service
    printf 'selected=%s\n' "$MODE"
    ;;
  status)
    printf 'selected=%s\nrunning=%s\n' "$(current_mode || true)" "$(running_mode || true)"
    ;;
  *) echo "usage: minitz-qwen-mode {38|status}" >&2; exit 2 ;;
esac
