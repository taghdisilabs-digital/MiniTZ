# MiniTZ Single Task Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one living `TASK_PROGRAM.json` task array the only persisted MiniTZ task/order/status authority, add durable worker claims, bounded context policy, capability closure, late packaging, and a clean packaged-OS launch gate.

**Architecture:** Extend the existing `minitz_task_program.py` adapter rather than create a second scheduler. Persist all authoritative task state inside each `tasks[]` row; synthesize legacy pointers only in memory. Apply the owner-approved future-horizon rewrite transactionally while preserving the current UNIFY-10 task bytes/digest.

**Tech Stack:** Python 3.12, JSON, pytest, existing MiniTZ atomic file/lock/digest primitives.

**Spec:** `docs/superpowers/specs/2026-09-12-minitz-single-task-authority-design.md`

## Global Constraints

- `TASK_PROGRAM.json` is the only persisted task/order/status/progression authority.
- Preserve current `UNIFY-10` task definition/digest and do not start the production executor.
- Canonical new lifecycle: `PENDING -> WORKING -> COMPLETE`.
- Packaging is blocked by capability closure; packaged OS launch is tested immediately after package creation.
- Default task context is token-bounded and task-local; expand by exact reference only.

---

### Task 1: Single-list adapter semantics
- [ ] Add failing tests for non-persisted compatibility pointer, strict array-order current task, `WORKING`, worker claims, and completion.
- [ ] Implement minimal adapter changes and run focused tests.

### Task 2: Future-horizon evolution
- [ ] Add failing tests for preserving the current task while rewriting only future rows.
- [ ] Implement transactional future-horizon rewrite with digest/dependency validation.
- [ ] Stage the revised live program copy and validate it before live write.

### Task 3: Owner capability/package/launch sequence
- [ ] Add missing detailed capability-review/migration tasks and `CAP-CLOSE-01`.
- [ ] Move packaging after capability/system readiness and insert `OS-LAUNCH-01` immediately after it.
- [ ] Add task-local context/worker policy to future active tasks.

### Task 4: Live apply and verification
- [ ] Atomically apply one owner-authorized program revision.
- [ ] Verify exact readback, current task preservation, no persisted `current_execution`, single WORKING maximum, dependency/order invariants, and packaging/launch ordering.
- [ ] Refresh only derived projections from the living program; do not enable/start the executor.
