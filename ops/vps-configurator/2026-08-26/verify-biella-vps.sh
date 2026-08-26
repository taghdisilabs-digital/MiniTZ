#!/usr/bin/env bash
# Biella VPS verifier — read-only verification companion.
set -u

echo '=== IDENTITY ==='; whoami; hostnamectl
echo; echo '=== STORAGE / MEMORY ==='; lsblk -o NAME,SIZE,TYPE,FSTYPE,FSVER,MOUNTPOINTS,MODEL; df -h /; free -h; swapon --show; printf 'swappiness='; cat /proc/sys/vm/swappiness; grep '^/swapfile ' /etc/fstab || true
echo; echo '=== UBUNTU PRO ==='; pro status || true
echo; echo '=== ROOT SSH ==='; sshd -T 2>/dev/null | grep -E 'permitrootlogin|pubkeyauthentication' || true
echo; echo '=== CORE TOOLS ==='
for x in git gh node npm python3 pip3 cargo rustc go java docker psql aws codex cmake ninja clang ffmpeg blender pandoc rclone; do printf '%-14s ' "$x"; command -v "$x" || echo MISSING; done
echo; echo '=== SERVICES ==='; printf 'docker: '; systemctl is-active docker 2>/dev/null || true; printf 'postgresql: '; systemctl is-active postgresql 2>/dev/null || true
echo; echo '=== EVIDENCE ==='; echo /root/biella/evidence/host-install.log; echo /root/biella/evidence/host-install-failures.log; [ -f /root/biella/evidence/host-install-failures.log ] && cat /root/biella/evidence/host-install-failures.log || true
