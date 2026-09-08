# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v9

task:
  id: D17-02
  project: Biella Games
  section: post_d01
  class: hard_creation
  title: Prove traversal and camera quality
  status: PENDING
  runner: READY
  priority: GAME_FIRST

  authority:
    - Mahdi Taghdisi current product/execution authority
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - projects/biella-games/docs/PRODUCTION.md
    - docs/project-state/07_BIELLA_PRODUCTION_SYSTEM.md
    - docs/task-program/D_NEXT_100_TASKS.json (active entry only; not a queue)

  continuity:
    completed_predecessor: D17-01
    production_source: projects/biella-games/docs/PRODUCTION.md

  preserve:
    - all completed predecessor tasks and their evidence
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one-repository/one-controller/one-Project-production-source architecture

  stop: Execute only D17-02; validate and persist it before advancing.
```
