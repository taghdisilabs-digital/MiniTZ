# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v14

task:
  id: D04-01
  project: Biella Games
  section: post_d01
  class: hard_creation
  title: Data-driven content system multiplication
  status: PENDING
  runner: READY

  authority:
    - Mahdi Taghdisi latest explicit instruction
    - current observed execution state
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - projects/biella-games/docs/PRODUCTION.md

  continuity:
    completed_predecessor: D03-01
    predecessor_status: COMPLETE_OWNER_ACCEPTED
    production_source: projects/biella-games/docs/PRODUCTION.md
    source_alignment_gate: VERIFIED_GITHUB_MAIN_PRE_EXECUTION_AND_POST_TURN_FAIL_CLOSED
    task_session: FRESH_PER_NEW_TASK

  preserve:
    - all completed predecessor tasks and accepted evidence
    - all committed D03-01 improvements and exact proof
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one repository, one controller, one current task
    - customer/project isolation

  execution_directive:
    mode: RUN_D04_01_HIGHEST_QUALITY_NONBLOCKING
    execution: Start D04-01 immediately. Task class describes complexity only and is not a blocker or approval gate.
    acceptance: Use only the exact D04-01 task contract and latest owner direction. Do not invent new completion gates or broaden scope.
    continue_rule: CONTINUE requires an exact unmet acceptance criterion and the smallest executable next action.
    completion_rule: When the exact acceptance contract is satisfied, return COMPLETE immediately; controller persists and advances automatically.
    monitor_rule: Do not spend model turns narrating or repeatedly polling a productive external process; let the deterministic resource call finish and classify its result immediately.
    reuse_rule: Reuse verified outputs and cached compact context; never redo passed work without material invalidation.

  routing:
    authoritative_quality: HIGHEST_QUALITY_ELIGIBLE_STRONG_ROUTE
    preferred_model: gpt-reserve
    preferred_reasoning: max
    local_or_free_fit_resources: PREFER_WHEN_CORRECT_AND_NONBLOCKING
    bounded_fallback_closure: FORBIDDEN
    quota_probe: FORBIDDEN

  isolation:
    customer_cells: PAUSED_FOR_BIELLA_PRODUCTION
    project_data_leakage: FORBIDDEN
    observer_or_chat_hook_required_for_progress: false

  stop: Continue D04-01 automatically until durable closure, a new customer lease, or a newer Mahdi instruction changes execution state.
```
