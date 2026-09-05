# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v7

task:
  id: BIELLA-CONSOLIDATION-2026-09-05
  objective: >
    Consolidate Biella Git, Drive, feeder state, control UI, and local workspace
    into one canonical production authority without losing completed or in-progress work.

  authority:
    - Mahdi explicit approval in current execution
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - docs/superpowers/specs/2026-09-05-biella-ai-production-map-task-contract-design.md
    - docs/migration/ONE_REPO_PROVENANCE_2026-09-05.md

  read:
    - current biella-engine main and consolidation branch
    - preserved Games commit 2193b769e61b43ebfc4f910f6380c68e6b828cd5
    - stranded Website/control commit b621a0680c5586a1502558efb81ff084f8d1da74
    - capability-preparation commit aa718584a99c0cee1884488bb4dafec4d2e94c05
    - future AAA-SF commit 297129637fded33dc0e3636954645e5655803928
    - current canonical Drive roots and file IDs

  write:
    - canonical monorepo source under /root/biella/repos/biella-engine after merge
    - current-state and active-task continuity
    - projects/biella-games/docs/PRODUCTION.md
    - controller/feeder/control/website paths required by consolidation
    - canonical Drive navigation and continuity records

  preserve:
    - all D01-001 through D01-026 completion/evidence plus the pending D01-027 partial source preserved before cutover
    - P3/P4 durable Engine evidence already accepted
    - P4-06 as INCOMPLETE_DEFERRED, not complete
    - current Games/Website/capability/AAA-SF preserved source identities
    - existing Drive file identities where canonicals are moved

  must:
    - one active Git repository after closure
    - one canonical local repo root after closure
    - one durable Project task/section source, not a feeder completion ledger
    - automatic control liveness from observed runtime heartbeat/service state
    - semantic task deduplication before adding future work
    - prune only proven redundant recovery/backup/worktree copies

  must_not:
    - execute D01-027 or overwrite its preserved partial source during consolidation
    - restart the automated feeder before consolidation qualification
    - delete unique source/evidence/progress
    - claim P4-06 or Foundation complete
    - promote historical or Project-specific source into Engine authority implicitly

  acceptance:
    - monorepo contains verified Engine, Games, Website/control, reusable schema/reference inputs
    - Games progress reads 26/50 with D01-027 next and no D01-027 completion claim
    - Engine/controller/website/Games migration validation passes
    - GitHub main remote readback matches exact final commit/tree
    - Drive current state and navigation read back with preserved canonical IDs
    - superseded copies are removed only after unique-value verification

  validate:
    - Python feeder/control/monorepo/continuity tests
    - unified Codex controller/runtime contracts
    - Website build and control browser/contracts
    - Games verify_demo01.py
    - Unreal 5.8.2 Editor build and headless launch from projects/biella-games
    - exact GitHub and Drive remote readback

  persist:
    - patrickminitz-web/biella-engine main
    - Drive root ID 1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7
    - existing 03/04 Drive file identities
    - migration provenance in canonical Git/Drive

  stop: >
    Stop after consolidation is durably verified and 04 has been replaced with
    D01-027 after final verification. Do not execute Games production in this task.
```
