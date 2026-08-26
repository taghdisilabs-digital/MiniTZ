# 55 — Task Handoff & Continuation Notes

## Purpose
A durable handoff surface so a new Codex/agent session can continue from exact repository and execution truth without relying on conversation memory.

## Required detailed content
1. **Current task identity** — prompt/task ID, phase, objective, status, and exact task boundary.
2. **Repository truth** — repository, branch, source commit/tree, result commit/tree, remote, and worktree status.
3. **Files changed** — exact paths with created/modified/deleted classification and concise purpose.
4. **Tests executed** — commands, test counts, pass/fail results, duration, evidence class, and failing test names.
5. **Interfaces created or changed** — exact names, signatures, types, schemas, and compatibility notes.
6. **Migrations/state changes** — migration IDs, schema versions, durable state mutations, and rollback/continuation notes.
7. **Artifacts/evidence** — exact references, digests, storage locations, runtime identities, screenshots/builds where applicable.
8. **Known limitations** — concrete unimplemented or partially implemented behavior.
9. **Unresolved facts and blockers** — exact unknowns, what was attempted, and unaffected work already completed.
10. **Next dependency** — next required task plus exact continuation instructions and preconditions.
11. **Decision timeline** — important implementation decisions, failures, repairs, and recovery events.
12. **Reality classification** — REAL, REFERENCE, MOCK, or NOT_RUN for significant evidence.

## BIELLA VISUAL LOCK
Transparent background. Deep graphite/navy panels. Violet dominant accent. Cyan secondary. Green/amber/red semantic status only. Thin technical borders, restrained glow, compact engineering typography.

## Acceptance
A new worker can recover exact continuation state from this file plus the repository without needing the previous chat session.
