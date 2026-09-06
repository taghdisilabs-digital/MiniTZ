# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v11

task:
  id: D03-01
  project: Biella Games
  section: post_d01
  class: hard_creation
  title: Production rendering, animation, VFX, and audio quality
  status: RUNNING
  runner: RUNNING

  authority:
    - Mahdi Taghdisi latest explicit instruction, 2026-09-06
    - current observed execution state
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - projects/biella-games/docs/PRODUCTION.md

  continuity:
    completed_predecessor: D02-04
    production_source: projects/biella-games/docs/PRODUCTION.md
    task_session_id: 01a07480-2c40-7d03-b649-d3f72807cc3e
    attempt: 42
    runner_pid: 2126038
    codex_child_pid: 2228063
    model: gpt-6-astra
    reasoning: ultra
    current_increment: FOOT_CONTACT_CORRECTION_IN_PROGRESS
    last_verified_increment_commit: 1898b568bf6c6dceae9dcf6aa66ef7a45a6f6e1d

  preserve:
    - all completed predecessor tasks and exact evidence
    - all verified D03-01 rendering, animation, readability, and audio/VFX increments
    - current D03-01 foot-contact implementation, tests, diagnostics, and outputs
    - current task/session identity and task memory
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one-repository/one-controller/one-current-task architecture
    - unrelated source/configuration without mutation

  execution_directive:
    mode: CONTINUE_CURRENT_D03_01_SESSION_FROM_PRESERVED_STATE
    preservation: Reuse every valid existing output; never restart, rollback, or redo verified work without material invalidation.
    current_scope: Finish the remaining D03-01 work and task-derived validation only.
    recovery: On failure, repair/rerun only the smallest invalidated boundary and preserve unaffected verified work.
    volatile_state_rule: Never use 03/04 byte identity as a gameplay/runtime validation gate; they are volatile observer/continuity state.
    local_ai_rule: Local Qwen is optional on-demand assistance and must never block the authoritative Codex turn.
    progression: After D03-01 durable closure, automatically advance to the earliest unfinished task in projects/biella-games/docs/PRODUCTION.md and continue in canonical file order.
    continuous_queue: Continue one task at a time through every unfinished canonical task until the current list is exhausted.
    no_intertask_stop: Do not stop merely because a task completed, a model/session changed, a viewer opened/closed, or an optional Resource failed.
    no_skip: Do not skip an earlier unfinished canonical task unless Mahdi explicitly changes priority/order.
    no_redo: Do not rerun completed/verified work unless material input/source/artifact/validation/contract/authority is invalidated.
    list_exhausted: Request a new task from Mahdi; absent a new task, perform bounded read-only discovery over current projects and registered capabilities.

  ordered_queue:
    source: projects/biella-games/docs/PRODUCTION.md
    current: D03-01
    completed: 59
    total: 168
    selection_rule: EARLIEST_UNFINISHED_IN_CANONICAL_ORDER
    concurrency: ONE_AUTHORITATIVE_TASK_WITH_SAFE_RESOURCE_PARALLELISM

  observer_surfaces:
    public_live: READ_ONLY
    private_control: READ_ONLY
    opening_closing_reconnecting: MUST_NOT_SIGNAL_OR_INTERRUPT_ENGINE

  stop: Continue automatically after durable closure. Stop only for a genuine required dependency/authority boundary or exhausted list with no authorized next work.
```
