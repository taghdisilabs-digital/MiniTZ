# Biella VPS — Verified Clean-Host State — 2026-08-26

This is the actual clean-host state observed after the successful installation and reboot. It is evidence, not a universal Biella hardware requirement.

## Verified host

- root SSH key login: PASS
- `permitrootlogin prohibit-password`
- `pubkeyauthentication yes`
- Amazon EC2 `c5a.4xlarge`
- Ubuntu 26.04.1 LTS
- kernel `7.0.0-1011-aws`
- x86_64
- 16 logical CPUs, AMD EPYC 7R32
- 30 GiB RAM

## Verified storage / memory

- 350 GiB Amazon EBS root disk
- 348.9 GiB ext4 root partition
- about 268 GiB available after creating the swap file
- `/swapfile` configured 64 GiB
- swap persisted after reboot
- swap used after reboot: 0 B
- `/etc/fstab`: `/swapfile none swap sw 0 0`
- `vm.swappiness=10`
- `growpart /dev/nvme0n1 1`: `NOCHANGE`
- `resize2fs /dev/nvme0n1p1`: filesystem already full-size / nothing to do

## Verified Ubuntu Pro

- `esm-apps`: enabled
- `esm-infra`: enabled
- `livepatch`: enabled

## Verified tool paths

```text
git            /usr/bin/git
gh             /usr/bin/gh
node           /usr/bin/node
npm            /usr/bin/npm
python3        /usr/bin/python3
pip3           /usr/bin/pip3
cargo          /usr/bin/cargo
rustc          /usr/bin/rustc
go             /usr/bin/go
java           /usr/bin/java
docker         /usr/bin/docker
psql           /usr/bin/psql
aws            /usr/bin/aws
codex          /root/.local/bin/codex
cmake          /usr/bin/cmake
ninja          /usr/bin/ninja
clang          /usr/bin/clang
ffmpeg         /usr/bin/ffmpeg
blender        /usr/bin/blender
pandoc         /usr/bin/pandoc
rclone         /usr/bin/rclone
```

## Verified services

- Docker: active
- PostgreSQL: active

## Verified installer result

The successful staged run showed no entries under `failed/skipped packages`.

Evidence paths on the host:

- `/root/biella/evidence/host-install.log`
- `/root/biella/evidence/host-install-failures.log`
