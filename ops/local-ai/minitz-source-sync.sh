#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPO_ROOT="${MINITZ_REPO_ROOT:-/root/attached-storage/minitz-os-sandbox/workspace/repo}"
readonly REMOTE_REF="refs/remotes/origin/main"
readonly MINITZ_SOURCE_SYNC_INSTALLER="${MINITZ_SOURCE_SYNC_INSTALLER:-}"

fail() {
  printf 'MiniTZ source alignment blocked: %s\n' "$*" >&2
  exit 75
}

if systemctl is-active --quiet minitz-on.target; then
  fail "MiniTZ is already ON; source alignment is allowed only during an OFF-to-ON transition"
fi

handoff_source_repair() {
  printf 'SOURCE_RECONCILIATION_REQUIRED: %s; preserve local bytes and repair inside the current executor task\n' "$*"
  refresh_installed_controller
  exit 0
}

refresh_installed_controller() {
  [[ -z "$MINITZ_SOURCE_SYNC_INSTALLER" ]] && return 0
  [[ -x "$MINITZ_SOURCE_SYNC_INSTALLER" ]] || fail "aligned controller installer missing: $MINITZ_SOURCE_SYNC_INSTALLER"
  "$MINITZ_SOURCE_SYNC_INSTALLER" >/dev/null
}

[[ -d "$REPO_ROOT/.git" ]] || fail "canonical Git checkout missing at $REPO_ROOT"
branch="$(git -C "$REPO_ROOT" branch --show-current)"
[[ "$branch" == "main" ]] || fail "canonical checkout is on branch $branch, expected main"

if ! GIT_TERMINAL_PROMPT=0 timeout 25s git -C "$REPO_ROOT" fetch --quiet origin main; then
  # A transport outage does not invalidate the retained canonical Git objects.
  git -C "$REPO_ROOT" rev-parse --verify HEAD^{tree} >/dev/null || fail "local source objects unavailable"
  if git -C "$REPO_ROOT" show-ref --verify --quiet "$REMOTE_REF"; then
    git -C "$REPO_ROOT" merge-base --is-ancestor "$REMOTE_REF" HEAD || handoff_source_repair "known remote revision needs reconciliation"
  fi
  refresh_installed_controller
  printf 'REMOTE_UNAVAILABLE_LOCAL_CONTINUATION: retained local source; publication will retry independently\n'
  exit 0
fi
local_head="$(git -C "$REPO_ROOT" rev-parse HEAD)"
remote_head="$(git -C "$REPO_ROOT" rev-parse "$REMOTE_REF")"

if [[ "$local_head" == "$remote_head" ]]; then
  refresh_installed_controller
  printf 'MiniTZ source aligned at %s\n' "$local_head"
  exit 0
fi

if git -C "$REPO_ROOT" merge-base --is-ancestor "$remote_head" "$local_head"; then
  refresh_installed_controller
  printf 'MiniTZ source has preserved local progress ahead of origin/main: %s\n' "$local_head"
  exit 0
fi

if ! git -C "$REPO_ROOT" merge-base --is-ancestor "$local_head" "$remote_head"; then
  handoff_source_repair "local main and origin/main diverged; automatic history rewrite is forbidden"
fi

python3 - "$REPO_ROOT" "$local_head" "$remote_head" <<'PY' || handoff_source_repair "remote paths overlap preserved local work"
from pathlib import PurePosixPath
import subprocess
import sys

repo, local_head, remote_head = sys.argv[1:]
status = subprocess.check_output(
    ["git", "-C", repo, "status", "--porcelain=v1", "-z", "--untracked-files=all"]
)
dirty: set[str] = set()
for record in status.split(b"\0"):
    if len(record) >= 4:
        dirty.add(record[3:].decode("utf-8", errors="surrogateescape"))
changed_raw = subprocess.check_output(
    ["git", "-C", repo, "diff", "--name-only", "-z", f"{local_head}..{remote_head}"]
)
changed = {
    item.decode("utf-8", errors="surrogateescape")
    for item in changed_raw.split(b"\0") if item
}

def overlaps(left: str, right: str) -> bool:
    a = PurePosixPath(left).parts
    b = PurePosixPath(right).parts
    n = min(len(a), len(b))
    return a[:n] == b[:n]

hits = sorted({d for d in dirty for c in changed if overlaps(d, c)})
if hits:
    print(
        "MiniTZ source alignment blocked: remote update overlaps preserved dirty paths: "
        + ", ".join(hits),
        file=sys.stderr,
    )
    raise SystemExit(1)
PY

git -C "$REPO_ROOT" merge --ff-only --quiet "$REMOTE_REF" || handoff_source_repair "safe fast-forward needs exact-path reconciliation"
new_head="$(git -C "$REPO_ROOT" rev-parse HEAD)"
[[ "$new_head" == "$remote_head" ]] || fail "post-fast-forward HEAD does not match origin/main"
refresh_installed_controller
printf 'MiniTZ source fast-forwarded safely to %s\n' "$new_head"
