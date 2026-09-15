# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /state/task-program/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 99
  program_sha256: 0bb5b8d9ae4bdfe0a9c8beb8d2bf05206ecc66d3e523de4068091a6a3b4bf924
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
  id: MINITZ-OWNER-ACCEPTANCE-01
  task_revision: 1
  task_sha256: 6daf33252c3e9cd8d67179301b36075618488c7cfc5e26ccf42b32abbf3a6a85
  lane: Engine
  state: PENDING
  runner: READY
  runtime_state_source: /root/attached-storage/minitz-os-sandbox/state/production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-SYSTEM-QUALIFY-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 503b3ac5d475179b77f642ad31962bc114d69e24f919eda01fd110f909d5c914
  predecessor_program_revision: 98
  predecessor_program_sha256: a53707a16860c18ba71cc380c1ae7b15e9fe1813daafacaee4bf4c172ea47c7d
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 41613404a81879b927d2491f7b0308a2d2425645582bdbddc067bed8c35ed754

progress:
  completed_tasks: 34
  active_tasks: 2
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
