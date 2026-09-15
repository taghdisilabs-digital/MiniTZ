# MiniTZ system qualification — task revision 7

The current full build passes the required non-boot qualification. Raw-image runtime boot is deferred to owner/final acceptance under task revision 7 and was not executed.

- Source: 195 files, `07fc3844ab80c41d8bc6e4825386a3491a8de0347428b56eeabb2cc838d781e9`.
- Canonical image: `MiniTZ-OS-07fc3844ab80c41d.raw`, 3,758,096,384 bytes, SHA-256 `2353fbe2c932c43120938bcd27ca103f231825f2f978741078e9ce12f73a1080`.
- Current checks: 32 affected tests; GPT/EFI/ext4/kernel/source structure; all 195 embedded source files; installed desktop/network/VPN packages and configuration; signed full-source clean installation, idempotent reapply, seven CLI calls and fresh-process recovery.
- Reused evidence: unchanged core, integration, attachments, privacy and real Chromium local-fixture behavior. See `reuse-bindings.json` for exact hashes, changed boundaries and historical test counts.
- `nonboot-observations.json` preserves diagnostic Needs Attention/Needs Setup and unobserved runtime capabilities. Package presence is not live desktop/VPN proof; process recovery is not a machine restart.
- Earlier failed attempts and superseded artifacts remain historical in `failure-dispositions.json`. The truncated output was restored from the exact verified build copy; its corruption trigger remains unestablished.

The canonical report is `../MINITZ-SYSTEM-QUALIFY-01.validation.json`. This directory is evidence, not a task-progression authority.
