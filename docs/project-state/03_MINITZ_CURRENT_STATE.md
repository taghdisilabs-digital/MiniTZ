# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 96
  program_sha256: dbb227888d2745eec7ff7cd47b78a4782955f9fb76b76240bf1078c4419f98d3
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
  id: MINITZ-BOOTABLE-IMAGE-01
  task_revision: 4
  task_sha256: ac02353555b069e178e697845b4f86e158b6aaa6acd72f9add19d8e18e6cbc91
  lane: Engine
  state: WORKING
  runner: READY
  runtime_state_source: /root/attached-storage/minitz-os-sandbox/state/production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-GITHUB-MAIN-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 889fcb4e98bb0b8186e044f2305467f7c9b8671f3448e70f5c46212db7e4871b
  predecessor_program_revision: 92
  predecessor_program_sha256: 9294c91b7ad866c403e96c87907c5dd047ce837b280be7384a360c948c2efa44
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 32c8d32e03970d2841503dad769b8c4a7161e56a8fd4292bc6dbc2cd5109d667

progress:
  completed_tasks: 32
  active_tasks: 4
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
