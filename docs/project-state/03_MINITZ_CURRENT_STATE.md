# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 113
  program_sha256: cbd5c08fb66f42aa64e454816acd9dd4a25bc1713b47d45914b60a7e33209daa
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
  id: MINITZ-FINAL-CLOSURE-01
  task_revision: 6
  task_sha256: 0c96033b1c0d570e963adcca177ab1ace7011781482acb18eb4d235d6f50e100
  lane: Engine
  state: WORKING
  runner: READY
  runtime_state_source: /root/attached-storage/minitz-os-sandbox/state/production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-OWNER-ACCEPTANCE-01
  predecessor_task_revision: 6
  predecessor_task_sha256: 21dd149a0495522c194507c4e047725bb1526e909a2973926f91a8fc0b34b8e5
  predecessor_program_revision: 111
  predecessor_program_sha256: 6e4058865ad8a240c55a43f4be9964b20a8ce62cdee70369dda67ddeace71ca6
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 1c1442dbfe5b208b5b786dc4ab4a95d921f585565df14872ea06210d2054e0b2

progress:
  completed_tasks: 35
  active_tasks: 1
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
