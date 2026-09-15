#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_DIR="$ROOT_DIR/tests/fixtures"
TEST_ROOT="$(mktemp -d /tmp/minitz-local-ai-smoke.XXXXXX)"
trap 'rm -rf -- "$TEST_ROOT"' EXIT
install -d "$TEST_ROOT/bin"
install -m 755 "$FIXTURE_DIR/bin/curl" "$TEST_ROOT/bin/curl"
PATH="$TEST_ROOT/bin:$PATH" \
  MINITZ_QWEN_MODEL=qwen3-coder-next:minitz \
  MINITZ_QWEN_READY_TIMEOUT_SECONDS=2 \
  bash "$ROOT_DIR/ops/workstation/minitz-qwen-ready.sh"
grep -Fq 'qwen3-coder-next:minitz' "$ROOT_DIR/ops/workstation/minitz-qwen-residency.sh"
grep -Fq 'MINITZ_QWEN_RESIDENCY_INTERVAL_SECONDS=5' "$ROOT_DIR/ops/workstation/minitz-qwen-residency.service"
grep -Fq 'minitz-ollama.service' "$ROOT_DIR/ops/workstation/minitz-qwen-residency.service"
grep -Fq 'on) exec "$RUNTIME" on' "$ROOT_DIR/ops/local-ai/minitz-ai-start.sh"
! grep -Fqi 'qwen3-coder-next:biella' "$ROOT_DIR/ops/workstation/minitz-qwen-residency.sh"
bash -n "$ROOT_DIR/ops/workstation/minitz-qwen-ready.sh"
bash -n "$ROOT_DIR/ops/workstation/minitz-qwen-residency.sh"
bash -n "$ROOT_DIR/ops/local-ai/minitz-ai-start.sh"
printf 'local AI runtime smoke: PASS\n'
