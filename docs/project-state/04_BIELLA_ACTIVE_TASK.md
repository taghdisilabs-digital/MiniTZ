# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v8

task:
  id: D01-030
  project: Biella Games
  section: demo01
  class: hard
  title: Add rival weapon use and damage response
  status: PENDING
  execution_started: false
  feeder: STOPPED_BY_OWNER

  authority:
    - Mahdi Taghdisi current product/execution authority
    - projects/biella-games/AGENTS.md
    - projects/biella-games/docs/PRODUCTION.md

  continuity:
    production_source: projects/biella-games/docs/PRODUCTION.md
    completed_predecessor: D01-029
    implementation_commit: 780b064e8d6440b84f65b9c818bfb800187c7f2d
    implementation_tree: c9b3ccfab394f22563b98aef768da06e43cc6af9
    github_readback: VERIFIED_EXACT_MAIN_AND_ALL_13_CHANGED_FILES
    predecessor_evidence: projects/biella-games/Build/Demo01/D01-029-acceptance.md
    source_runtime_identity: projects/biella-games/Build/Demo01/D01-029-validation.json

  preserve:
    - D01-001 through D01-029 completion in canonical PRODUCTION.md
    - existing rival targeting and weapon source, including preserved partial later-task behavior
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one-repository/one-controller/one-Project-production-source architecture

  stop: >
    The explicit D01-029 task boundary is complete. D01-030 is only the next
    canonical pending task; no D01-030 implementation or acceptance has been
    executed by this run. The feeder remains stopped by owner. Continue only
    under a subsequent owner instruction or authorized production execution.
```
