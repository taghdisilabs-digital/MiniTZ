# Next 10 Autonomous Task Guides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use TDD and verification-before-completion.

**Goal:** Make the next ten canonical game tasks executable without artificial owner/setup/review stalls while preserving real runtime and quality acceptance.

**Architecture:** Keep PRODUCTION.md order unchanged. Harden D17-01..08 in place, create current D19-01/02 guides from their accepted objectives, point the execution map at those current guides, and refresh exact source digests.

**Tech Stack:** Markdown task guides, JSON execution map, Python/pytest.

**Spec:** docs/project-state/07_BIELLA_PRODUCTION_SYSTEM.md

## Global Constraints
- Executor owns routine blockers and reversible setup.
- No review/approval/sign-off waiting stages.
- Real runtime, measured performance, external capability and quality evidence remain required where the task claims them.
- Reuse valid evidence; no wholesale rerun or rebuild without invalidation.
- PRODUCTION.md remains the only execution-order authority.

### Task 1
- [ ] Add failing tests covering all next-ten current guides and map digests.
- [ ] Harden/create the ten current guides.
- [ ] Refresh execution-map source references and derived ledger/readable map.
- [ ] Run scoped and regression verification; commit/push/read back; restore the frozen production session.
