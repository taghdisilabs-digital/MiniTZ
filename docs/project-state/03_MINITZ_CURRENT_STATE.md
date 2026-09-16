# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 137
  program_sha256: a805f81dd35a7d7b41e41923f32df635eb9cb441500c2b1a81070df0331e4a1d
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
  id: D17-04
  task_revision: 1
  task_sha256: c0b1dc0fd420b99a38369b065740ae9062f71837ae050462c1beff4d00b6a8e9
  lane: Games
  state: PENDING
  runner: READY
  runtime_state_source: /root/attached-storage/minitz-os-sandbox/state/production/runtime.json

transition_receipt:
  predecessor_task_id: D17-03
  predecessor_task_revision: 2
  predecessor_task_sha256: 0da9ec2cda4ce1f0ecf67ffa67b9fab75da52684b4a0e99a444277f6afbe95c3
  predecessor_program_revision: 136
  predecessor_program_sha256: 8d70fd2b5a79163aa3bc70603e1013707589a6f72bd07a1a76f1bb07a8f3b814
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 441d10cf1a5d66622e5a4c887c00e9de37eb1a18d4b38e9bca56dc540a50331d

progress:
  completed_tasks: 38
  active_tasks: 8
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
