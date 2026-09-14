# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 92
  program_sha256: 9294c91b7ad866c403e96c87907c5dd047ce837b280be7384a360c948c2efa44
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
  canonical_checkout: /root/attached-storage/minitz-os-sandbox/workspace/repo
  source_identity_source: LIVE_GIT_READ_REQUIRED

active_execution:
  id: MINITZ-GITHUB-MAIN-01
  task_revision: 2
  task_sha256: 889fcb4e98bb0b8186e044f2305467f7c9b8671f3448e70f5c46212db7e4871b
  lane: Engine
  state: WORKING
  runner: READY
  runtime_state_source: /root/attached-storage/minitz-os-sandbox/state/production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-INSTALL-UPDATE-01
  predecessor_task_revision: 2
  predecessor_task_sha256: f8a451ce1d57258e239e26b2c407b02b17934952ae3ed7349ab8644b6a26a75e
  predecessor_program_revision: 88
  predecessor_program_sha256: 94295234a5cadb9f126615b844367f3fc5d4a4a5a0f5e220d559e93ee3374f1e
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 64e1049fc8c02638f994038c38cf3960adf6e52ad8459a0df3eb9fb8ef14f859

progress:
  completed_tasks: 31
  active_tasks: 5
  total_tasks: 36

execution_invariants:
  one_task_program: true
  derived_ledgers_authority: false
  runner_and_auto_feeder_source: MINITZ_TASK_PROGRAM_ONLY
  hidden_task_queue_allowed: false
  generic_scheduler_progression_mutation: false
  publication_cursor_authority: false
  local_qwen_authority: false
```
