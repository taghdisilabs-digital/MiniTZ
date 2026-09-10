# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 46
  program_sha256: 6a464e96bcbebe15b4ce5fb5d98b4cf1bfcfa00122137205b597420f9297c31c
  task_program_authority: true
  production_execution_authority: true
  production_order_status_authority: true

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

repository:
  repository: taghdisilabs-digital/MiniTZ
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  source_identity_source: LIVE_GIT_READ_REQUIRED

active_execution:
  id: UNIFY-04
  task_revision: 5
  task_sha256: 7c2aa788be82e8c4f7520125edb6b9a3f4e8b0c49b7a145cfa31525b78e07e32
  lane: Engine
  state: PENDING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

progress:
  completed_tasks: 14
  active_tasks: 786
  total_tasks: 800

execution_invariants:
  one_task_program: true
  derived_ledgers_authority: false
  runner_and_auto_feeder_source: MINITZ_TASK_PROGRAM_ONLY
  hidden_task_queue_allowed: false
  generic_scheduler_progression_mutation: false
  publication_cursor_authority: false
  local_qwen_authority: false
```
