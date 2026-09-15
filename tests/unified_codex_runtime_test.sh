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


mkdir -p "$tmp/repo/src/minitz_os" "$tmp/repo/ops/local-ai"
cat > "$tmp/repo/src/minitz_os/__init__.py" <<'PYMOD'
MARKER = "SEALED_OR_REPO_SOURCE_VISIBLE"
PYMOD
cat > "$tmp/repo/ops/local-ai/minitz_local_capacity.py" <<'PYLOCAL'
MARKER = "LOCAL_AI_SOURCE_VISIBLE"
PYLOCAL
cat > "$tmp/python-runner" <<'PYRUN'
#!/usr/bin/env python3
import minitz_os
import minitz_local_capacity
print(minitz_os.MARKER)
print(minitz_local_capacity.MARKER)
PYRUN
chmod +x "$tmp/python-runner"
python_out="$(MINITZ_REPO_ROOT="$tmp/repo" MINITZ_PYTHON_SOURCE_ROOT="$tmp/repo" MINITZ_AI_RUNTIME_ENV="$tmp/runtime.env" MINITZ_PRODUCTION_RUNNER="$tmp/python-runner" "$root/ops/local-ai/minitz-codex.sh" production status)"
grep -Fq 'SEALED_OR_REPO_SOURCE_VISIBLE' <<<"$python_out"
grep -Fq 'LOCAL_AI_SOURCE_VISIBLE' <<<"$python_out"


mkdir -p "$tmp/sandbox/system/current/opt/minitz/source/src/minitz_os" \
         "$tmp/sandbox/system/current/opt/minitz/source/ops/local-ai" \
         "$tmp/sandbox/workspace/repo"
cat > "$tmp/sandbox/system/current/opt/minitz/source/src/minitz_os/__init__.py" <<'PYSEALED'
MARKER = "SEALED_DEFAULT_VISIBLE"
PYSEALED
cat > "$tmp/sandbox/system/current/opt/minitz/source/ops/local-ai/minitz_local_capacity.py" <<'PYSEALEDLOCAL'
MARKER = "SEALED_LOCAL_VISIBLE"
PYSEALEDLOCAL
cat > "$tmp/env-runner" <<'PYENV'
#!/usr/bin/env python3
import os
import minitz_os
import minitz_local_capacity
print("REPO=" + os.environ.get("MINITZ_REPO_ROOT", ""))
print("PROJECT=" + os.environ.get("MINITZ_PROJECT_ROOT", ""))
print("TASK_PROGRAM=" + os.environ.get("MINITZ_TASK_PROGRAM_PATH", ""))
print("RUNTIME=" + os.environ.get("MINITZ_RUNTIME_ROOT", ""))
print(minitz_os.MARKER)
print(minitz_local_capacity.MARKER)
PYENV
chmod +x "$tmp/env-runner"
default_out="$(MINITZ_OS_SANDBOX_ROOT="$tmp/sandbox" MINITZ_AI_RUNTIME_ENV="$tmp/runtime.env" MINITZ_PRODUCTION_RUNNER="$tmp/env-runner" "$tmp/bin/minitz-codex" production status)"
grep -Fq "REPO=$tmp/sandbox/workspace/repo" <<<"$default_out"
grep -Fq "PROJECT=$tmp/sandbox/workspace/repo" <<<"$default_out"
grep -Fq "TASK_PROGRAM=$tmp/sandbox/state/task-program/TASK_PROGRAM.json" <<<"$default_out"
grep -Fq "RUNTIME=$tmp/sandbox/state/production" <<<"$default_out"
grep -Fq 'SEALED_DEFAULT_VISIBLE' <<<"$default_out"
grep -Fq 'SEALED_LOCAL_VISIBLE' <<<"$default_out"

echo 'unified codex runtime: PASS'
