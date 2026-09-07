#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPO_ROOT="${BIELLA_REPO_ROOT:-/root/biella/repos/biella-engine}"
readonly REMOTE_REF="refs/remotes/origin/main"
readonly BIELLA_SOURCE_SYNC_INSTALLER="${BIELLA_SOURCE_SYNC_INSTALLER:-}"

fail() {
  printf 'Biella source alignment blocked: %s\n' "$*" >&2
  exit 75
}

refresh_installed_controller() {
  [[ -z "$BIELLA_SOURCE_SYNC_INSTALLER" ]] && return 0
  [[ -x "$BIELLA_SOURCE_SYNC_INSTALLER" ]] || fail "aligned controller installer missing: $BIELLA_SOURCE_SYNC_INSTALLER"
  "$BIELLA_SOURCE_SYNC_INSTALLER" >/dev/null
}

[[ -d "$REPO_ROOT/.git" ]] || fail "canonical Git checkout missing at $REPO_ROOT"
branch="$(git -C "$REPO_ROOT" branch --show-current)"
[[ "$branch" == "main" ]] || fail "canonical checkout is on branch $branch, expected main"

git -C "$REPO_ROOT" fetch --quiet origin main || fail "cannot fetch origin/main"
local_head="$(git -C "$REPO_ROOT" rev-parse HEAD)"
remote_head="$(git -C "$REPO_ROOT" rev-parse "$REMOTE_REF")"

if [[ "$local_head" == "$remote_head" ]]; then
  refresh_installed_controller
  printf 'Biella source aligned at %s\n' "$local_head"
  exit 0
fi

if git -C "$REPO_ROOT" merge-base --is-ancestor "$remote_head" "$local_head"; then
  refresh_installed_controller
  printf 'Biella source has preserved local progress ahead of origin/main: %s\n' "$local_head"
  exit 0
fi

if ! git -C "$REPO_ROOT" merge-base --is-ancestor "$local_head" "$remote_head"; then
  fail "local main and origin/main diverged; automatic history rewrite is forbidden"
fi

python3 - "$REPO_ROOT" "$local_head" "$remote_head" <<'PY' || exit 75
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
        "Biella source alignment blocked: remote update overlaps preserved dirty paths: "
        + ", ".join(hits),
        file=sys.stderr,
    )
    raise SystemExit(1)
PY

git -C "$REPO_ROOT" merge --ff-only --quiet "$REMOTE_REF" || fail "safe fast-forward failed"
new_head="$(git -C "$REPO_ROOT" rev-parse HEAD)"
[[ "$new_head" == "$remote_head" ]] || fail "post-fast-forward HEAD does not match origin/main"
refresh_installed_controller
printf 'Biella source fast-forwarded safely to %s\n' "$new_head"
