# MiniTZ Final Unification Implementation Plan

> **For agentic workers:** Execute inline against the owner-authorized canonical `main`; no parallel branch/repo is permitted.

**Goal:** Eliminate legacy product/provider authority from the active MiniTZ OS while preserving useful capabilities, experience, task continuity, and exact source history.

**Architecture:** The attached-drive MiniTZ sandbox owns source, task program, runtime state, memory, credentials, UI, build and release. Ubuntu 24.04 host services are external implementation resources only and are not MiniTZ authority. Removed integrations are absent rather than disabled/renamed.

**Tech Stack:** Python 3, shell, Docker, systemd source definitions, pytest, Git/GitHub.

## Global Constraints
- MiniTZ remains OFF for source edits; Ubuntu 24.04 host OS and unrelated apps are untouched.
- Exactly one canonical source repository: private `taghdisilabs-digital/MiniTZ`, branch `main` only.
- Preserve useful capability code and durable memory; remove legacy identity/authority.
- Remove pause/customer-handoff gates, AGY/Antigravity/Gemini integration, and Google Drive/rclone integration.
- Migrate active task/run/memory state from legacy host/runtime paths into `/root/attached-storage/minitz-os-sandbox/state`.
- No raw credential values enter source, logs, prompts, or public artifacts.

### Task 1: Canonical MiniTZ state authority
- Copy current Task Program into `state/task-program/TASK_PROGRAM.json` and normalize live authority/path refs.
- Copy durable production memory/task/evidence state into `state/production`, excluding Drive packages and pause artifacts.
- Update runtime/startup/task-program defaults/tests to use MiniTZ state paths only.
- Validate exact task count/status/current task and memory digests.

### Task 2: Delete pause/handoff authority
- Remove all pause/off request/ack files and statuses from runner/startup.
- Use graceful SIGTERM lifecycle only; finish active turn before exit, claim no new task.
- Remove obsolete customer-handoff service/module from active installation.
- Tests must prove no pause file/status can affect production.

### Task 3: Remove AGY/Gemini and Google Drive
- Delete AGY/Antigravity/Gemini routing, status, UI, provider registry, tests and documentation from active surfaces.
- Delete Google Drive/rclone publication, packaging, credentials, gates, runbooks and tests from active surfaces.
- Keep GitHub exact-main publication and other independent providers/capabilities intact.

### Task 4: MiniTZ-native runtime identity
- Rename active production/runtime modules, scripts, services, env keys and public UI from legacy product identity to MiniTZ.
- Move reusable capability package from `src/biella` into `src/minitz_os` and update imports.
- Remove active legacy paths/names; provenance may remain only under explicitly inert archive/provenance material.

### Task 5: Qualification and release
- Run focused then full current MiniTZ tests plus forbidden-identity scan.
- Verify one private GitHub repo/main-only and exact commit/tree readback.
- Seal/install current source, start MiniTZ ON, verify live dashboard/task progression/local AI/Commander and no removed integration/gate appears.
