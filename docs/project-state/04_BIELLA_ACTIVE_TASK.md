# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v8

task:
  id: D01-029
  project: Biella Games
  section: demo01
  class: hard
  title: Add rival navigation and combat positioning
  status: PENDING
  execution_started: false
  feeder: STOPPED_BY_OWNER

  objective: >
    Prove the rival contestant performs real gameplay positioning/navigation relative
    to its selected target, reusing the already-preserved rival source and evidence
    and implementing only any materially missing delta.

  authority:
    - Mahdi Taghdisi current product/execution authority
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - projects/biella-games/AGENTS.md
    - projects/biella-games/docs/PRODUCTION.md

  read:
    - projects/biella-games/Source/BiellaGames/Public/BiellaRival.h
    - projects/biella-games/Source/BiellaGames/Private/BiellaRival.cpp
    - projects/biella-games/Source/BiellaGames/Private/BiellaGamesGameModeBase.cpp
    - projects/biella-games/Build/Demo01/D01-029-editor.log
    - projects/biella-games/Build/Demo01/D01-029-runtime.log
    - docs/migration/evidence/MONOREPO_GAMES_QUALIFICATION_2026-09-05.md

  write:
    - projects/biella-games/Source/BiellaGames/Public/BiellaRival.h only if a missing delta requires it
    - projects/biella-games/Source/BiellaGames/Private/BiellaRival.cpp only if a missing delta requires it
    - projects/biella-games/Source/BiellaGames/Private/BiellaGamesGameModeBase.cpp only if spawn/ownership needs repair
    - projects/biella-games/Build/Demo01/D01-029-* task-derived evidence
    - projects/biella-games/docs/PRODUCTION.md after acceptance

  preserve:
    - D01-001 through D01-028 accepted completion and evidence
    - existing ABiellaRival source and current D01-029 logs
    - migration-observed RIVAL_POSITION evidence as evidence, not an automatic completion claim
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one-repository/one-controller/one-Project-production-source architecture

  must:
    - reobserve current D01-029 source and evidence before writing
    - return COMPLETE_ALREADY without reimplementation if current evidence already satisfies acceptance
    - otherwise execute only the materially missing positioning/navigation delta
    - use biella resource routing when a specialized configured Resource reduces model work or improves quality
    - run real UE 5.8.2 build/runtime validation tied to current source

  must_not:
    - reopen or redo D01-001 through D01-028 without material invalidation evidence
    - mark D01-029 complete solely because migration qualification observed RIVAL_POSITION
    - begin D01-030 before durable D01-029 acceptance
    - create another repo, feeder ledger, scheduler, controller, or Project state authority
    - manage or redeem Codex usage/reset/credits

  acceptance:
    - editable rival source has explicit target-relative movement/positioning behavior
    - current runtime proves rival positioning with target identity and positioning mode/distance evidence
    - positioning behavior is compatible with rival targeting and combat without invalidating prior Demo tasks
    - current UE 5.8.2 Editor build succeeds
    - no fatal/assert/unhandled exception/segfault in bounded runtime qualification

  validate:
    - python3 projects/biella-games/tests/verify_demo01.py
    - /opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh BiellaGamesEditor Linux Development
    - bounded non-root Unreal runtime with D01_SIGNAL RIVAL_POSITION evidence
    - affected Engine/feeder/control tests only if shared source changes

  persist:
    - patrickminitz-web/biella-engine main
    - projects/biella-games/docs/PRODUCTION.md
    - exact task-derived evidence under projects/biella-games/Build/Demo01/
    - Drive CURRENT continuity with existing 03/04 file IDs

  stop: >
    After D01-029 is durably accepted or correctly marked COMPLETE_ALREADY, advance
    canonical production to D01-030 and stop at that boundary unless Mahdi has
    explicitly authorized continued production execution.
```
