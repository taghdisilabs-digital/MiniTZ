#!/usr/bin/env bash
set -Eeuo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/runtime.env" <<'ENV'
CODEX_HOME=/tmp/old-model-home
BIELLA_TEST_API_TOKEN=loaded
ENV
cat > "$tmp/codex" <<'SH'
#!/usr/bin/env bash
printf 'PWD=%s\n' "$PWD"
printf 'CODEX_HOME=%s\n' "${CODEX_HOME:-}"
printf 'TOKEN=%s\n' "${BIELLA_TEST_API_TOKEN:+SET}"
printf 'ARGS='; printf '%q ' "$@"; printf '\n'
SH
chmod +x "$tmp/codex"
cat > "$tmp/feeder" <<'SH'
#!/usr/bin/env bash
printf 'FEEDER_ARGS='; printf '%q ' "$@"; printf '\n'
SH
chmod +x "$tmp/feeder"
out="$(BIELLA_AI_RUNTIME_ENV="$tmp/runtime.env" BIELLA_CODEX_BIN="$tmp/codex" "$root/ops/local-ai/biella-codex.sh" -m gpt-test probe)"
grep -Fq 'PWD=/root' <<<"$out"
grep -Fq 'CODEX_HOME=/root/.codex' <<<"$out"
grep -Fq 'TOKEN=SET' <<<"$out"
grep -Fq -- '--dangerously-bypass-approvals-and-sandbox' <<<"$out"
grep -Fq -- '-m gpt-test probe' <<<"$out"
echo 'unified codex runtime: PASS'

feed_out="$(BIELLA_AI_RUNTIME_ENV="$tmp/runtime.env" BIELLA_CODEX_BIN="$tmp/codex" BIELLA_CODEX_FEEDER="$tmp/feeder" "$root/ops/local-ai/biella-codex.sh" feed status --run-id demo01-50)"
grep -Fq 'FEEDER_ARGS=status --run-id demo01-50' <<<"$feed_out"
