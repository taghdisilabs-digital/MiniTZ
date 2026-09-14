#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# -ge 1 ]] || { echo "usage: $0 BOOST-01..BOOST-05 [command...]" >&2; exit 2; }
BOOSTER="$1"
shift
case "$BOOSTER" in BOOST-01|BOOST-02|BOOST-03|BOOST-04|BOOST-05) ;; *) echo "invalid Booster: $BOOSTER" >&2; exit 2 ;; esac
SANDBOX="${MINITZ_OS_SANDBOX_ROOT:-/root/attached-storage/minitz-os-sandbox}"
RUNTIME="${MINITZ_RUNTIME_ROOT:-$SANDBOX/state/production}"
BOOSTROOT="${MINITZ_BOOST_WORK_ROOT:-$SANDBOX/state/boost-work-program}"
WORKTREE="$SANDBOX/workspace/boosts/$BOOSTER"
[[ -d "$WORKTREE" ]] || { echo "Booster workspace is not prepared: $WORKTREE" >&2; exit 3; }
mkdir -p "$SANDBOX/output/$BOOSTER" "$SANDBOX/state/$BOOSTER"
[[ $# -gt 0 ]] || set -- bash
exec docker run --rm --gpus all --runtime=nvidia --hostname "minitz-$BOOSTER" \
  --pids-limit 2048 --shm-size 4g \
  -v "$SANDBOX/workspace/boosts/$BOOSTER:/workspace/repo:rw" -v "$SANDBOX/output/$BOOSTER:/output:rw" -v "$SANDBOX/state/$BOOSTER:/state:rw" \
  -v /usr:/host-vps/usr:ro -v /bin:/host-vps/bin:ro -v /sbin:/host-vps/sbin:ro -v /lib:/host-vps/lib:ro -v /lib64:/host-vps/lib64:ro -v /boot:/host-vps/boot:ro \
  -v /etc/os-release:/host-vps/etc/os-release:ro -v /etc/systemd:/host-vps/etc/systemd:ro -v /etc/apt:/host-vps/etc/apt:ro -v /var/lib/dpkg:/host-vps/var/lib/dpkg:ro \
  -v $SANDBOX/state/task-program/TASK_PROGRAM.json:/minitz-live/TASK_PROGRAM.json:ro \
  -v "$BOOSTROOT/BOOSTER_TASK_LIST.json:/minitz-live/BOOSTER_TASK_LIST.json:ro" -v "$BOOSTROOT/context/$BOOSTER.json:/minitz-live/BOOSTER_CONTEXT.json:ro" \
  -v "$RUNTIME/memory/compacted-memory.json:/minitz-live/compacted-memory.json:ro" -v "$RUNTIME/memory/current-task.json:/minitz-live/current-task.json:ro" \
  -v "$BOOSTROOT/local-ai/$BOOSTER:/minitz-local-ai:ro" \
  -w /workspace/repo minitz-os-lab:ubuntu26.04 "$@"
