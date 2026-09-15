#!/usr/bin/env bash
set -Eeuo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/runtime.env" <<'ENV'
CODEX_HOME=/tmp/old-model-home
MINITZ_TEST_API_TOKEN=loaded
ENV
cat > "$tmp/codex" <<'SH'
#!/usr/bin/env bash
printf 'PWD=%s\n' "$PWD"
printf 'CODEX_HOME=%s\n' "${CODEX_HOME:-}"
printf 'HOME=%s\n' "${HOME:-}"
printf 'GH_CONFIG_DIR=%s\n' "${GH_CONFIG_DIR:-}"
printf 'TOKEN=%s\n' "${MINITZ_TEST_API_TOKEN:+SET}"
printf 'ARGS='; printf '%q ' "$@"; printf '\n'
SH
chmod +x "$tmp/codex"
cat > "$tmp/runner" <<'SH'
#!/usr/bin/env bash
printf 'PRODUCTION_ARGS='; printf '%q ' "$@"; printf '\n'
SH
chmod +x "$tmp/runner"
out="$(env -u HOME -u GH_CONFIG_DIR MINITZ_AI_RUNTIME_ENV="$tmp/runtime.env" MINITZ_CODEX_BIN="$tmp/codex" "$root/ops/local-ai/minitz-codex.sh" -m gpt-test probe)"
grep -Fq 'PWD=/root' <<<"$out"
grep -Fq 'CODEX_HOME=/root/.codex' <<<"$out"
grep -Fq 'HOME=/root' <<<"$out"
grep -Fq 'GH_CONFIG_DIR=/root/.config/gh' <<<"$out"
grep -Fq 'TOKEN=SET' <<<"$out"
grep -Fq -- '--dangerously-bypass-approvals-and-sandbox' <<<"$out"
grep -Fq -- '-m gpt-test probe' <<<"$out"

auto_out="$(MINITZ_AI_RUNTIME_ENV="$tmp/runtime.env" MINITZ_CODEX_BIN="$tmp/codex" MINITZ_PRODUCTION_RUNNER="$tmp/runner" "$root/ops/local-ai/minitz-codex.sh" production status)"
grep -Fq 'PRODUCTION_ARGS=status' <<<"$auto_out"

mkdir -p "$tmp/installed" "$tmp/bin"
cp "$root/ops/local-ai/minitz-codex.sh" "$tmp/installed/minitz-codex.sh"
ln -s "$tmp/installed/minitz-codex.sh" "$tmp/bin/minitz-codex"
symlink_out="$(MINITZ_AI_RUNTIME_ENV="$tmp/runtime.env" MINITZ_CODEX_BIN="$tmp/codex" MINITZ_PRODUCTION_RUNNER="$tmp/runner" "$tmp/bin/minitz-codex" production status)"
grep -Fq 'PRODUCTION_ARGS=status' <<<"$symlink_out"


mkdir -p "$tmp/repo/src/minitz_os"
cat > "$tmp/repo/src/minitz_os/__init__.py" <<'PYMOD'
MARKER = "SEALED_OR_REPO_SOURCE_VISIBLE"
PYMOD
cat > "$tmp/python-runner" <<'PYRUN'
#!/usr/bin/env python3
import minitz_os
print(minitz_os.MARKER)
PYRUN
chmod +x "$tmp/python-runner"
python_out="$(MINITZ_REPO_ROOT="$tmp/repo" MINITZ_AI_RUNTIME_ENV="$tmp/runtime.env" MINITZ_PRODUCTION_RUNNER="$tmp/python-runner" "$root/ops/local-ai/minitz-codex.sh" production status)"
grep -Fq 'SEALED_OR_REPO_SOURCE_VISIBLE' <<<"$python_out"

echo 'unified codex runtime: PASS'
