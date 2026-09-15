# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 112
  program_sha256: 9df5cd3f6a0522ae0ec0f9c9654e85b2748d48357d3cf7cb305582356ad1913d
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
  task_revision: 5
  task_sha256: 01b64348a27aeabb1ec99a2b8e8be9f1f64b18256ab52059f8cfaff99866d5ff
  lane: Engine
  state: PENDING
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
