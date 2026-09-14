#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_DIR="$ROOT_DIR/tests/fixtures"
TEST_ROOT="$(mktemp -d /tmp/biella-ai-smoke.XXXXXX)"
RUNTIME_ROOT="$TEST_ROOT/runtime"
STATE_ROOT="$TEST_ROOT/state"
LOG_ROOT="$TEST_ROOT/log"
MARKER="$TEST_ROOT/codex-mcp-path"
FAKE_TOKEN="smoke-token-not-a-production-secret"
FAKE_CF_TOKEN="smoke-cloudflare-token-not-a-production-secret"
FAKE_CF_ACCOUNT="0123456789abcdef0123456789abcdef"

cleanup() {
  if [[ -f "$STATE_ROOT/cloudflared.pid" ]]; then
    kill "$(<"$STATE_ROOT/cloudflared.pid")" 2>/dev/null || true
  fi
  rm -rf -- "$TEST_ROOT"
}
trap cleanup EXIT

install -d -m 700 "$RUNTIME_ROOT" "$STATE_ROOT" "$LOG_ROOT" "$TEST_ROOT/bin"
install -m 755 "$FIXTURE_DIR/bin/curl" "$FIXTURE_DIR/bin/codex" "$FIXTURE_DIR/bin/cloudflared" "$FIXTURE_DIR/bin/systemctl" "$TEST_ROOT/bin/"
ln -s "$ROOT_DIR/ops/local-ai/biella-ai-start.sh" "$TEST_ROOT/bin/biella-ai-start"
printf 'SATURN_BASE_URL=https://saturn.example.invalid\nSATURN_TOKEN=%q\nCLOUDFLARE_ACCOUNT_ID=%q\nCLOUDFLARE_API_TOKEN=%q\nCLOUDFLARE_TUNNEL_TOKEN=\nCLOUDFLARE_CONFIGURED=1\n' \
  "$FAKE_TOKEN" "$FAKE_CF_ACCOUNT" "$FAKE_CF_TOKEN" > "$RUNTIME_ROOT/runtime.env"
chmod 600 "$RUNTIME_ROOT/runtime.env"

set +e
OUTPUT="$(PATH="$TEST_ROOT/bin:$PATH" \
  PYTHONPATH="$FIXTURE_DIR${PYTHONPATH:+:$PYTHONPATH}" \
  FAKE_CODEX_MCP_MARKER="$MARKER" \
  BIELLA_AI_RUNTIME_ROOT="$RUNTIME_ROOT" \
  BIELLA_AI_STATE_ROOT="$STATE_ROOT" \
  BIELLA_AI_LOG_ROOT="$LOG_ROOT" \
  BIELLA_GATEWAY_URL="http://127.0.0.1:8787" \
  "$TEST_ROOT/bin/biella-ai-start" 2>&1)"
EXIT_CODE=$?
set -e

[[ "$EXIT_CODE" -eq 0 ]] || {
  printf '%s\n' "$OUTPUT" >&2
  exit 1
}
grep -F --quiet -- 'READY' <<< "$OUTPUT"
grep -F --quiet -- 'Saturn:       CONNECTED (1 resources, 1 instance types)' <<< "$OUTPUT"
grep -F --quiet -- 'Cloudflare:   CONNECTED (account-api)' <<< "$OUTPUT"
grep -F --quiet -- 'Codex:        READY (Saturn MCP registered; use biella-codex)' <<< "$OUTPUT"
grep -F --quiet -- 'Gateway:      NOT_VERIFIED' <<< "$OUTPUT"
grep -F --quiet -- 'saturn_resource_count=1' "$STATE_ROOT/status.env"
grep -F --quiet -- 'qwen_gpu_layers=38' "$STATE_ROOT/status.env"
grep -F --quiet -- 'qwen_cpu_ram_target_gib=40' "$STATE_ROOT/status.env"
grep -F --quiet -- 'cloudflare_account_api=VERIFIED' "$STATE_ROOT/status.env"
[[ "$(stat -c '%a' "$RUNTIME_ROOT/runtime.env")" == "600" ]]
! grep -R -F --quiet -- "$FAKE_TOKEN" "$STATE_ROOT" "$LOG_ROOT" "$MARKER"
! grep -R -F --quiet -- "$FAKE_CF_TOKEN" "$STATE_ROOT" "$LOG_ROOT" "$MARKER"

printf 'local AI runtime smoke: PASS\n'
