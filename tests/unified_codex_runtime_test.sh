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
cat > "$tmp/runner" <<'SH'
#!/usr/bin/env bash
printf 'PRODUCTION_ARGS='; printf '%q ' "$@"; printf '\n'
SH
chmod +x "$tmp/runner"
out="$(BIELLA_AI_RUNTIME_ENV="$tmp/runtime.env" BIELLA_CODEX_BIN="$tmp/codex" "$root/ops/local-ai/biella-codex.sh" -m gpt-test probe)"
grep -Fq 'PWD=/root' <<<"$out"
grep -Fq 'CODEX_HOME=/root/.codex' <<<"$out"
grep -Fq 'TOKEN=SET' <<<"$out"
grep -Fq -- '--dangerously-bypass-approvals-and-sandbox' <<<"$out"
grep -Fq -- '-m gpt-test probe' <<<"$out"

auto_out="$(BIELLA_AI_RUNTIME_ENV="$tmp/runtime.env" BIELLA_CODEX_BIN="$tmp/codex" BIELLA_PRODUCTION_RUNNER="$tmp/runner" "$root/ops/local-ai/biella-codex.sh" production status)"
grep -Fq 'PRODUCTION_ARGS=status' <<<"$auto_out"

mkdir -p "$tmp/installed" "$tmp/bin"
cp "$root/ops/local-ai/biella-codex.sh" "$tmp/installed/biella-codex.sh"
ln -s "$tmp/installed/biella-codex.sh" "$tmp/bin/biella-codex"
symlink_out="$(BIELLA_AI_RUNTIME_ENV="$tmp/runtime.env" BIELLA_CODEX_BIN="$tmp/codex" BIELLA_PRODUCTION_RUNNER="$tmp/runner" "$tmp/bin/biella-codex" production status)"
grep -Fq 'PRODUCTION_ARGS=status' <<<"$symlink_out"

echo 'unified codex runtime: PASS'
