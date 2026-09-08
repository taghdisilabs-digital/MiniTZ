# Progressive Resource Blocker Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use TDD and verification-before-completion.

**Goal:** Stop unchanged external-resource blockers from consuming repeated strong-model turns while preserving the blocked task/session and immediately advancing independent GAME_FIRST work.

**Architecture:** Keep `PRODUCTION.md` as the only execution order. When owner-current order places independent work ahead of the blocked resource requirement, persist per-task Codex session identities so parked tasks resume losslessly. For the current Win64 boundary, D17 becomes independent of D08's Windows-only criterion; D15 remains the first task that requires both D17 and D08 evidence.

**Tech Stack:** Python controller/state modules, JSON execution map, Markdown production/task guides, pytest.

**Spec:** `docs/project-state/07_BIELLA_PRODUCTION_SYSTEM.md` and `projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md`

## Global Constraints
- Preserve D08 source/evidence and persistent Codex session identity.
- Never mark D08 complete without Win64 evidence.
- `PRODUCTION.md` remains the single physical order; no second queue or scheduler.
- Do not repeat an unchanged `REQUIRES_OTHER_RESOURCE` turn when independent work is runnable.
- GitHub per-task and Drive batching remain unchanged.

### Task 1: Preserve task sessions across parked work
- [x] Add failing tests for per-task session registry and resumption.
- [x] Implement minimal session registry in `biella_production_runner.py`.
- [x] Run focused runner tests.

### Task 2: Remove D08 as a visual-work prerequisite
- [x] Add failing order/dependency tests: D17 follows D07; D08 remains pending before D15.
- [x] Reorder canonical production/maps/guides and regenerate ledger/current state.
- [x] Run priority/map/state tests.

### Task 3: Verify and resume
- [x] Run scoped production regression suite and `git diff --check` (127 passed).
- [ ] Commit/push/read back exact GitHub revision.
- [ ] Verify D08 capsule/session preservation and thaw the same controller.