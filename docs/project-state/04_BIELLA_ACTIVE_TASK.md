# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v9

task:
  id: D01-037
  project: Biella Games
  section: demo01
  class: creation
  title: Add gameplay HUD core
  status: PENDING
  runner: READY

  authority:
    - Mahdi Taghdisi current product/execution authority
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - projects/biella-games/docs/PRODUCTION.md

  continuity:
    completed_predecessor: D01-036
    production_source: projects/biella-games/docs/PRODUCTION.md

  preserve:
    - all completed predecessor tasks and their evidence
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one-repository/one-controller/one-Project-production-source architecture

  stop: Execute only D01-037; validate and persist it before advancing.
```
