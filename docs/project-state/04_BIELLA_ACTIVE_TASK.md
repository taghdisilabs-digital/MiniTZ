# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v8

task:
  id: D01-031
  project: Biella Games
  section: demo01
  class: hard
  title: Prove shared player/rival/infected interaction
  status: PENDING
  execution_started: false
  feeder: STOPPED_BY_OWNER

  authority:
    - Mahdi Taghdisi current product/execution authority
    - projects/biella-games/AGENTS.md
    - projects/biella-games/docs/PRODUCTION.md

  continuity:
    production_source: projects/biella-games/docs/PRODUCTION.md
    completed_predecessor: D01-030
    implementation_commit: 4a95e0fd829378beac6c6977f5ca5baec031446e
    implementation_tree: bed66704f847ad73915503f526384243c55fb389
    github_readback: VERIFIED_EXACT_MAIN_AND_ALL_16_CHANGED_FILES
    predecessor_evidence: projects/biella-games/Build/Demo01/D01-030-acceptance.md
    source_runtime_identity: projects/biella-games/Build/Demo01/D01-030-validation.json

  preserve:
    - D01-001 through D01-030 completion in canonical PRODUCTION.md
    - existing rival targeting, navigation, weapon and damage-response source and evidence
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one-repository/one-controller/one-Project-production-source architecture

  stop: >
    The explicit D01-030 task boundary is complete. D01-031 is only the next
    canonical pending task; no D01-031 implementation or acceptance has been
    executed by this run. The feeder remains stopped by owner. Continue only
    under a subsequent owner instruction or authorized production execution.
```
