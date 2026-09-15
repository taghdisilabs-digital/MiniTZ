# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 116
  program_sha256: 7227ea718518b0445618fc0dd228b3c608a902d36076ce461326806af32d0c5e
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
  id: MINITZ-SYSTEM-QUALIFY-01
  task_revision: 10
  task_sha256: 88b2ced7bcaf0396b2099edb958eeb4e15e45fc630497c1e2a5f1a349939985c
  lane: Engine
  state: WORKING
  runner: READY
  runtime_state_source: /root/attached-storage/minitz-os-sandbox/state/production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-BOOTABLE-IMAGE-01
  predecessor_task_revision: 4
  predecessor_task_sha256: ac02353555b069e178e697845b4f86e158b6aaa6acd72f9add19d8e18e6cbc91
  predecessor_program_revision: 96
  predecessor_program_sha256: dbb227888d2745eec7ff7cd47b78a4782955f9fb76b76240bf1078c4419f98d3
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 9daeb28d2eedca3db09615624c4d492a2477a0246846b9e4f42acd1d70414cbd

progress:
  completed_tasks: 33
  active_tasks: 3
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
