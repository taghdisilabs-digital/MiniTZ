#!/usr/bin/env bash
set -Eeuo pipefail
SANDBOX="${MINITZ_OS_SANDBOX_ROOT:-/mnt/biella-extra/minitz-os-sandbox}"
RUNTIME="${MINITZ_RUNTIME_ROOT:-/mnt/biella-extra/biella-runtime/codex-production}"
BOOSTROOT="${MINITZ_BOOST_WORK_ROOT:-/mnt/biella-extra/biella-runtime/boost-work-program}"
[[ $# -gt 0 ]] || set -- bash
exec docker run --rm \
  --gpus all --runtime=nvidia --hostname minitz-os-lab \
  --pids-limit 2048 --shm-size 4g \
  -v "$SANDBOX/workspace:/workspace:rw" -v "$SANDBOX/output:/output:rw" -v "$SANDBOX/state:/state:rw" \
  -v /usr:/host-vps/usr:ro -v /bin:/host-vps/bin:ro -v /sbin:/host-vps/sbin:ro \
  -v /lib:/host-vps/lib:ro -v /lib64:/host-vps/lib64:ro -v /boot:/host-vps/boot:ro \
  -v /etc/os-release:/host-vps/etc/os-release:ro -v /etc/systemd:/host-vps/etc/systemd:ro \
  -v /etc/apt:/host-vps/etc/apt:ro -v /var/lib/dpkg:/host-vps/var/lib/dpkg:ro \
  -v /root/biella/analysis/live_audit/TASK_PROGRAM.json:/minitz-live/TASK_PROGRAM.json:ro \
  -v "$BOOSTROOT/BOOSTER_TASK_LIST.json:/minitz-live/BOOSTER_TASK_LIST.json:ro" \
  -v "$RUNTIME/memory/compacted-memory.json:/minitz-live/compacted-memory.json:ro" \
  -v "$RUNTIME/memory/current-task.json:/minitz-live/current-task.json:ro" \
  -v "$BOOSTROOT/context:/minitz-context:ro" -v "$BOOSTROOT/local-ai:/minitz-local-ai:ro" \
  minitz-os-lab:ubuntu26.04 "$@"
