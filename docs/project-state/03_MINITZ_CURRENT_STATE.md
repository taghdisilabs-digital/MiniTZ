# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 128
  program_sha256: 6fe3d1e9c74c516a6e5553c758c7a29e4f40ce3f5dfd1c6dbd6dce3681fd2d46
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
  predecessor_task_revision: 8
  predecessor_task_sha256: d5fff2506163cd5389093153513d6a9bda5eb7ad1077faf7b343c227804495b8
  predecessor_program_revision: 127
  predecessor_program_sha256: 5e35ce190dddeed89ad6f4045c55ee061ee7ae5a2af87c9a87a3100adf376a57
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 48f2107ee44fe51929170dbba458b4c1dfd981fde6e1bd6f8b21718a03612c5f

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
