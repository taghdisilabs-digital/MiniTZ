# Biella Codex Usage-Aware Feeder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Maintain one sectioned Games production flow behind `biella-codex`, preserving progress and continuing from Demo 01 through Stage 8.

**Architecture:** One Python feeder, one durable `/root/biella/work/games-production.json`, one current task, and one systemd single-flight run. Sections are planned/audited just-in-time inside that same document.

**Tech Stack:** Python 3 standard library, Bash, Codex CLI, systemd-run, Git.

**Spec:** `docs/superpowers/specs/2026-09-04-biella-codex-usage-aware-feeder-design.md`

## Constraints
- `biella-codex` is the only AI/production entrypoint.
- Never invoke `/usage` or redeem resets.
- Creation never uses low reasoning.
- Astra Ultra handles hard/deep-memory/section planning and audit first.
- Preserve completed tasks; no overlapping write owner.
- No separate queue/state/batch/ledger authority.

### Task 1: Unified production document
- [x] Import Demo progress and Stage 2-8 sections into one production document.
- [x] Embed task status/evidence and current pointers in the same file.
- [x] Preserve completed tasks on sync/init.

### Task 2: Rolling section execution
- [x] Plan empty sections into 20-50 bounded tasks using deep-memory routing.
- [x] Execute one task at a time with usage-aware model fallback.
- [x] Audit the same section and append only remaining missing tasks.
- [x] Advance automatically through Stage 8.

### Task 3: Single interface and verification
- [x] Replace `init-demo01/--queue` with `init|sync|run|start|status|stop`.
- [x] Remove obsolete internal queue/state implementation.
- [ ] Run full feeder/controller/workstation regressions.
- [ ] Commit, push, remote-readback, install exact bytes, initialize one live production document.
- [ ] Leave execution stopped while the current Games controller owns the write boundary.
