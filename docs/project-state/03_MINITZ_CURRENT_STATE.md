# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 103
  program_sha256: 8cab9f4ab3527d1fa91bfd55a7de3012a1008721910a7a114c4450d0a08abd55
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
  id: NONE
  state: COMPLETE
  runner: STOPPED
  runtime_state_source: /root/attached-storage/minitz-os-sandbox/state/production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-FINAL-CLOSURE-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 647f0a29a212a351816d974f327aacc45d2e7ebff36cc6d5853c795347a95c0f
  predecessor_program_revision: 102
  predecessor_program_sha256: 8b592c1abcaa442a07da46848387eacee5ada453f6594c275321aa2496f2d499
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 1a9eee445ab576cf5f5671db9139c62e2ae205f0cbc6727463a7c7ddcfd60a79

progress:
  completed_tasks: 36
  active_tasks: 0
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
