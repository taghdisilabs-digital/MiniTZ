# Biella VPS Configurator — 2026-08-26

Frozen from the clean Biella AWS host setup that was actually executed and verified on 2026-08-26.

## What this package keeps

- root SSH with the existing EC2 key
- `/root/.codex`
- `/root/biella`
- Ubuntu 26.04 + Ubuntu Pro
- 64 GiB `/swapfile`, `vm.swappiness=10`
- Docker + PostgreSQL under `systemd`
- official AWS CLI v2
- official OpenAI Codex standalone installer
- Playwright-managed headless Chromium
- resumable stages under `/root/biella/.install-state`

## What it deliberately does not bring back

- `/srv/biella`
- `/home/ubuntu/biella-work` as active authority
- ubuntu/root ownership split for Biella
- NVIDIA/CUDA on a CPU-only host
- MiniTZ manager/critic/validator/worker services
- fixed GPU/provider/paid-service blockers
- old VPS assumptions

## Clean-server quick start — 8 commands maximum

1. `sudo -i`
2. Extract/copy this folder to `/root/biella/vps-configurator`
3. `bash /root/biella/vps-configurator/biella-vps-configurator.sh`
4. `reboot`
5. Reconnect directly as root, then `bash /root/biella/vps-configurator/verify-biella-vps.sh`
6. `codex login --device-auth`
7. `gh auth login && gh repo clone patrickminitz-web/biella-engine /root/biella/repos/biella-engine`
8. `tmux new-session -A -s biella` then run `cd /root/biella/repos/biella-engine && codex --dangerously-bypass-approvals-and-sandbox`

## Resume after any interruption

Run the same configurator again:

`bash /root/biella/vps-configurator/biella-vps-configurator.sh`

Completed stages are skipped. Logs remain at:

- `/root/biella/evidence/host-install.log`
- `/root/biella/evidence/host-install-failures.log`

## Official sources used

- Ubuntu 26.04 / Ubuntu Pro repositories for system packages
- AWS CLI v2: `https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip`
- OpenAI Codex: `https://chatgpt.com/codex/install.sh`
- Playwright + `@playwright/test` from npm; Chromium managed by Playwright

## Stable service split

`systemd`: SSH, Docker, PostgreSQL, Ubuntu Pro/Livepatch.

`tmux`: interactive Codex only. Future real Biella daemons should use `systemd`.
