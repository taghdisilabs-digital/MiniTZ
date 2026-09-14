# MiniTZ Control-Plane Bounded Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop unavailable resources and retry loops from becoming workload while preserving canonical MiniTZ progress, source state, memory, and evidence.

**Architecture:** Keep `TASK_PROGRAM.json` as sole progression authority. Add bounded resource-unavailable convergence in the production runner, finite/deduplicated publication retry state, atomic Task Program provenance recording, and read-only source-reconciliation evidence without resetting either workspace.

**Tech Stack:** Python 3.12, systemd, Git, pytest, JSON/JSONL durable state.

**Spec:** Owner-approved containment order in the 2026-09-12 conversation.

## Global Constraints
- Preserve canonical Task Program revision 66 unless an explicit task mutation is required.
- Never reset, clean, stash, hard-reset, or overwrite either Git workspace.
- Preserve task capsules, compacted memory, cache, evidence, and accepted completed work.
- Resource unavailability must converge to an explicit bounded state, not recovery-loop attempts.
- Publication retries require finite budget, deduplication/backoff, representative evidence, and escalation.
- Task Program mutation and provenance must be atomic or explicitly provenance-degraded.

---

### Task 1: Bound unavailable Codex resources
**Files:** `ops/local-ai/biella_production_runner.py`, `ops/local-ai/minitz_codex_account_pool.py`, `tests/test_production_runner.py`, `tests/test_codex_account_pool.py`
- [ ] Add failing tests for account-pool exit 78 / no eligible logged-in account converging to `BLOCKED_RESOURCE_UNAVAILABLE` without repeated attempts.
- [ ] Implement explicit resource-unavailability classification and bounded wait/recheck behavior.
- [ ] Verify current task/capsule/memory remain unchanged while blocked.

### Task 2: Bound publication retries
**Files:** `ops/local-ai/biella_publication.py`, `tests/test_production_evidence.py` or focused publication tests
- [ ] Add failing tests for deduplicated representative errors, finite retry budget, exponential backoff, and `ESCALATED` state.
- [ ] Implement bounded Git/Drive publication retry policy without changing canonical task status.
- [ ] Preserve first/fresh representative diagnostics and stop redundant failure-record amplification.

### Task 3: Repair Task Program provenance atomically
**Files:** `ops/local-ai/minitz_task_program.py`, `tests/test_minitz_task_program_evolution.py`
- [ ] Add failing tests that mutation cannot silently commit without a matching change-ledger record.
- [ ] Implement atomic program+provenance transaction or durable `PROVENANCE_DEGRADED` recovery marker on partial failure.
- [ ] Reconstruct missing revision provenance only from authoritative historical diffs/events; never roll back revision 66.

### Task 4: Capture source divergence as evidence, not a reset instruction
**Files:** `ops/local-ai/biella_production_runner.py`, targeted tests/evidence artifacts
- [ ] Persist exact HEAD, origin/main, merge-base, ahead/behind counts, and dirty/untracked summaries for both current workspaces.
- [ ] Keep source reconciliation non-destructive and non-authoritative.

### Task 5: Targeted regression qualification
- [ ] Run account/resource gating tests.
- [ ] Run recovery boundedness tests.
- [ ] Run publication retry tests.
- [ ] Run Task Program provenance tests.
- [ ] Verify completed unrelated tasks are untouched and current task remains `CODEX-L40-BRIDGE-01`.
- [ ] Verify service/runtime projections do not claim RUNNING when the production unit is stopped.
