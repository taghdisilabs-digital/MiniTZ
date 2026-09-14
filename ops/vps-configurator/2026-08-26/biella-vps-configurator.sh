#!/usr/bin/env bash
# Biella VPS Configurator — verified clean-host baseline (2026-08-26)
# Verified target: Ubuntu 26.04.1 LTS, AWS c5a.4xlarge, x86_64, root-owned Biella/Codex.
# Sources: Ubuntu/Ubuntu Pro, AWS CLI official distribution, OpenAI Codex official installer, Playwright npm.
# No /srv/biella, no ubuntu/root split, no GPU stack on this CPU host, no MiniTZ services/agents.

set -u
MINITZ_ROOT="/root/biella"
STATE="$MINITZ_ROOT/.install-state"
EVIDENCE="$MINITZ_ROOT/evidence"
LOG="$EVIDENCE/host-install.log"
FAIL="$EVIDENCE/host-install-failures.log"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root."
  exit 1
fi

mkdir -p "$MINITZ_ROOT"/{repos,work,projects,runs,objects,artifacts,checkpoints,evidence,migration,quarantine,cache,backups,tooling} "$STATE"
touch "$LOG" "$FAIL"
exec > >(tee -a "$LOG") 2>&1
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a

mark_done(){ touch "$STATE/$1.done"; }
is_done(){ [ -f "$STATE/$1.done" ]; }
apt_retry(){ apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=60 -o Acquire::https::Timeout=60 "$@"; }
install_one(){
  local pkg="$1"
  if dpkg -s "$pkg" >/dev/null 2>&1; then echo "[OK] $pkg"; return 0; fi
  if ! apt-cache show "$pkg" >/dev/null 2>&1; then echo "[UNAVAILABLE] $pkg"; echo "UNAVAILABLE $pkg" >> "$FAIL"; return 0; fi
  echo "[INSTALL] $pkg"
  if apt_retry install -y --no-install-recommends "$pkg"; then echo "[PASS] $pkg"; else echo "[FAIL] $pkg"; echo "FAILED $pkg" >> "$FAIL"; fi
}

stage_root_ssh(){
  is_done 00-root-ssh && return
  echo '=== STAGE 00 ROOT SSH ==='
  install -d -m 700 /root/.ssh
  if [ -s /home/ubuntu/.ssh/authorized_keys ]; then
    install -m 600 /home/ubuntu/.ssh/authorized_keys /root/.ssh/authorized_keys
  elif [ ! -s /root/.ssh/authorized_keys ]; then
    echo 'MANUAL root authorized_keys' >> "$FAIL"; return
  fi
  cat > /etc/ssh/sshd_config.d/99-biella-root.conf <<'EOF'
PermitRootLogin prohibit-password
PubkeyAuthentication yes
EOF
  if sshd -t; then systemctl reload ssh; mark_done 00-root-ssh; else echo 'FAILED sshd validation' >> "$FAIL"; fi
}

stage_pro(){
  is_done 01-ubuntu-pro && return
  echo '=== STAGE 01 UBUNTU PRO ==='
  if ! command -v pro >/dev/null 2>&1; then apt_retry update || return; install_one ubuntu-pro-client; fi
  if pro status 2>&1 | grep -qi 'not attached'; then
    echo 'Ubuntu Pro needs one interactive official pro attach flow.'
    pro attach || { echo 'Ubuntu Pro attachment incomplete; rerun later.'; return; }
  fi
  pro enable esm-apps >/dev/null 2>&1 || true
  pro enable esm-infra >/dev/null 2>&1 || true
  pro enable livepatch >/dev/null 2>&1 || true
  if pro status 2>&1 | grep -q 'esm-apps.*enabled' && pro status 2>&1 | grep -q 'esm-infra.*enabled' && pro status 2>&1 | grep -q 'livepatch.*enabled'; then mark_done 01-ubuntu-pro; fi
}

stage_swap(){
  is_done 02-swap && return
  echo '=== STAGE 02 64 GiB SWAP ==='
  if [ -f /swapfile ]; then
    b=$(stat -c '%s' /swapfile 2>/dev/null || echo 0)
    if [ "$b" -lt 68000000000 ]; then swapoff /swapfile 2>/dev/null || true; rm -f /swapfile; fi
  fi
  if [ ! -f /swapfile ]; then fallocate -l 64G /swapfile; chmod 600 /swapfile; mkswap /swapfile; fi
  swapon --show=NAME --noheadings 2>/dev/null | tr -d ' ' | grep -qx /swapfile || swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  printf 'vm.swappiness=10\n' > /etc/sysctl.d/99-biella-memory.conf
  sysctl -w vm.swappiness=10 >/dev/null
  mark_done 02-swap
}

stage_index(){ is_done 03-apt-index && return; echo '=== STAGE 03 APT INDEX ==='; apt_retry update && mark_done 03-apt-index; }

stage_core(){
  is_done 04-core && return
  echo '=== STAGE 04 CORE ==='
  local pkgs='build-essential cmake ninja-build clang lldb gdb pkg-config libssl-dev git git-lfs gh curl wget ca-certificates gnupg jq tree ripgrep fd-find shellcheck zip unzip p7zip-full unar zstd xz-utils libarchive-tools rsync rclone aria2 pv parallel tmux htop btop sysstat iotop-c ncdu lsof strace dnsutils file openssl python3 python3-pip python3-venv python3-dev python-is-python3 pipx nodejs npm rustc cargo golang-go default-jdk'
  for p in $pkgs; do install_one "$p"; done
  git lfs install --system || true
  mark_done 04-core
}

stage_runtime(){
  is_done 05-runtime && return
  echo '=== STAGE 05 RUNTIME / DB ==='
  for p in docker.io docker-buildx docker-compose-v2 postgresql postgresql-contrib sqlite3; do install_one "$p"; done
  command -v docker >/dev/null 2>&1 && systemctl enable --now docker || true
  command -v psql >/dev/null 2>&1 && systemctl enable --now postgresql || true
  mark_done 05-runtime
}

stage_production(){
  is_done 06-production && return
  echo '=== STAGE 06 PRODUCTION ==='
  local pkgs='ffmpeg imagemagick sox libsox-fmt-all mediainfo libimage-exiftool-perl pandoc poppler-utils qpdf ghostscript libreoffice blender graphviz tesseract-ocr xvfb fonts-dejavu-core fonts-liberation fonts-noto-core fonts-noto-color-emoji'
  for p in $pkgs; do install_one "$p"; done
  mark_done 06-production
}

stage_aws(){
  is_done 07-aws && return
  echo '=== STAGE 07 OFFICIAL AWS CLI ==='
  if command -v aws >/dev/null 2>&1; then aws --version; mark_done 07-aws; return; fi
  cd /tmp || return
  rm -rf aws awscliv2.zip
  if curl --retry 5 --retry-all-errors -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip && unzip -q awscliv2.zip && ./aws/install && command -v aws >/dev/null 2>&1; then aws --version; mark_done 07-aws; fi
}

stage_codex(){
  is_done 08-codex && return
  echo '=== STAGE 08 OFFICIAL OPENAI CODEX ==='
  export PATH="/root/.local/bin:$PATH"
  if command -v codex >/dev/null 2>&1; then codex --version; mark_done 08-codex; return; fi
  if curl --retry 5 --retry-all-errors -fsSL https://chatgpt.com/codex/install.sh -o /tmp/codex-install.sh && sh /tmp/codex-install.sh; then
    export PATH="/root/.local/bin:$PATH"
    grep -qxF 'export PATH="/root/.local/bin:$PATH"' /root/.bashrc || echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.bashrc
    grep -qxF 'export CODEX_HOME="/root/.codex"' /root/.bashrc || echo 'export CODEX_HOME="/root/.codex"' >> /root/.bashrc
    command -v codex >/dev/null 2>&1 && codex --version && mark_done 08-codex
  fi
}

stage_browser(){
  is_done 09-browser && return
  echo '=== STAGE 09 HEADLESS PLAYWRIGHT CHROMIUM ==='
  command -v npm >/dev/null 2>&1 || return
  mkdir -p "$MINITZ_ROOT/tooling/playwright"
  cd "$MINITZ_ROOT/tooling/playwright" || return
  [ -f package.json ] || npm init -y
  if npm install --save-dev playwright @playwright/test; then
    export PLAYWRIGHT_BROWSERS_PATH="$MINITZ_ROOT/tooling/playwright-browsers"
    grep -qxF 'export PLAYWRIGHT_BROWSERS_PATH="/root/biella/tooling/playwright-browsers"' /root/.bashrc || echo 'export PLAYWRIGHT_BROWSERS_PATH="/root/biella/tooling/playwright-browsers"' >> /root/.bashrc
    npx playwright install --with-deps chromium && mark_done 09-browser
  fi
}

summary(){
  echo '=== BIELLA VPS CURRENT STATE ==='
  echo '-- completed stages --'; ls -1 "$STATE" 2>/dev/null | sort || true
  echo '-- failed/unavailable --'; sort -u "$FAIL" 2>/dev/null || true
  echo '-- core tools --'
  for x in git gh node npm python3 pip3 cargo rustc go java docker psql aws codex cmake ninja clang ffmpeg blender pandoc rclone; do printf '%-14s ' "$x"; command -v "$x" || echo MISSING; done
  echo '-- services --'; systemctl is-active docker 2>/dev/null || true; systemctl is-active postgresql 2>/dev/null || true
  echo '-- memory --'; free -h; swapon --show; echo "swappiness=$(cat /proc/sys/vm/swappiness)"
  echo '-- Ubuntu Pro --'; pro status 2>/dev/null || true
  echo "LOG=$LOG"; echo "FAILURES=$FAIL"
}

stage_root_ssh
stage_pro
stage_swap
stage_index || true
stage_core
stage_runtime
stage_production
stage_aws
stage_codex
stage_browser
summary
