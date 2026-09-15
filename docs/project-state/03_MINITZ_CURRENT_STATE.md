# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 101
  program_sha256: 238c1f1204aa37a8016e4a32cdaedb1e4fdbd335ec6de17ba10006931b8e6712
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
  task_revision: 1
  task_sha256: f27a7198239b86733774e9c486e38c5bb965737463dc5a30fac85a9edd9da8d3
  lane: Engine
  state: PENDING
  runner: READY
  runtime_state_source: /root/attached-storage/minitz-os-sandbox/state/production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-OWNER-ACCEPTANCE-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 9b6cbdaa8f990bc7d6864e52aa6efc8422d414ba68fe969a502cda9c59d2120b
  predecessor_program_revision: 100
  predecessor_program_sha256: 2ebcabfe69efe4d8fcf796a8d62d72701f2e243ecc81972391f485dc57c49953
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: e28e324cf419ef1cff552a1a86025961e8b72c26298cbf0be93cbd3607cd714d

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
