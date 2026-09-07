# External Resource Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement lossless first-customer checkpoint/sleep and last-customer restore, sanitized blocked/finish lesson handoff, durable customer restart behavior, and non-stalling model recovery.

**Architecture:** Biella owns a root-only checkpoint/resume/import helper and cooperative runner pause file. The neutral broker calls fixed systemd lifecycle actions, reference-counts running customer containers, and never reads Biella state directly.

**Tech Stack:** Python 3.12, systemd, Docker CLI, Git, pytest/unittest.

**Spec:** `docs/superpowers/specs/2026-09-07-external-resource-handoff-design.md`

## Global Constraints
- Preserve `/root/biella/repos/biella-engine` and all D03 dirty bytes; no reset/clean/stash.
- Customer source, repository identity, brand, visuals, copy, and credentials never enter Biella memory/evidence.
- No quota/balance probing.
- Resume restores exact pre-customer service active/enabled state, not an assumed always-on state.
- Multiple simultaneous customers share one Biella sleep checkpoint.

---

### Task 1: Biella checkpoint/sleep/resume helper
**Files:** create `ops/local-ai/biella_customer_handoff.py`; modify runner/service installer tests.
- [ ] Add failing tests for checkpoint identity, dirty fingerprint, exact service restoration, running-customer refusal, and cooperative pause acknowledgement.
- [ ] Run focused tests and confirm RED.
- [ ] Implement the helper and runner pause boundary.
- [ ] Run focused tests and confirm GREEN.

### Task 2: Broker first/last customer lifecycle and restart recovery
**Files:** create broker `lifecycle.py`; modify `service.py`, `server.py`, `docker_runtime.py`, CLI/API/tests.
- [ ] Add failing tests for first-start acquire, second-start no duplicate acquire, last-stop release, start rollback, orphan reconciliation, and `restart=unless-stopped`.
- [ ] Run focused tests and confirm RED.
- [ ] Implement lifecycle adapter/reconciler and restart policy.
- [ ] Run focused/full broker tests and confirm GREEN.

### Task 3: Sanitized finished/blocked experience handoff
**Files:** modify broker service/API/CLI/lessons tests and Biella helper tests.
- [ ] Add failing tests proving only sanitized generic lessons reach the fixed handoff file and importer; customer identity/source/path/visual content stays rejected.
- [ ] Run RED; implement stop reason/lesson bundle and Biella import; run GREEN.

### Task 4: Routing recovery
**Files:** modify `biella_codex_routing.py`, `biella_production_runner.py`, routing/runner tests.
- [ ] Add failing tests for catalog-discovered `gpt-reserve` and per-model account cooldown.
- [ ] Run RED; implement minimal routing changes; run GREEN.

### Task 5: Install, deploy, and live verification
**Files:** modify Biella and broker installers/systemd/operations docs as required.
- [ ] Run complete Biella and broker test/contract suites.
- [ ] Commit exact scoped files in each repository without D03/customer worktree content.
- [ ] Push/read back Biella GitHub commits; retain broker local commit identity if no remote exists.
- [ ] Install exact committed runtime bytes and compare SHA-256.
- [ ] Adopt current running customer set into one checkpoint without waking Biella.
- [ ] Verify D03 hashes, customer containers, source alignment, Drive continuity, and no failed units.
