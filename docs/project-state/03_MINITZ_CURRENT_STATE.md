# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 135
  program_sha256: 18f0a071f33620774f0ec1ed429ff938ae5e7bc21739a5f313ebb0e77cdf4f10
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
  id: D17-03
  task_revision: 1
  task_sha256: b790a40977db8a36d3948bbe2a43eaffea3735341a4c29fe092e9d8e098b7403
  lane: Games
  state: PENDING
  runner: READY
  runtime_state_source: /root/attached-storage/minitz-os-sandbox/state/production/runtime.json

transition_receipt:
  predecessor_task_id: D17-02
  predecessor_task_revision: 2
  predecessor_task_sha256: a4a56cb1c031979fd006ef521eb4e8673980b7440f5aea58f7e460b16aa36c75
  predecessor_program_revision: 134
  predecessor_program_sha256: f171ee415cd6e7a8b98f4908d434da2870ea2496993aaaa57c41e0927987f2ec
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 7e9b4bb20fb21af4ea3c8c2878b2081f6f072ad1d171c0d090469f27c9155675

progress:
  completed_tasks: 37
  active_tasks: 9
  total_tasks: 46

execution_invariants:
  one_task_program: true
  derived_ledgers_authority: false
  runner_and_auto_feeder_source: MINITZ_TASK_PROGRAM_ONLY
  hidden_task_queue_allowed: false
  generic_scheduler_progression_mutation: false
  publication_cursor_authority: false
  local_qwen_authority: false
```
