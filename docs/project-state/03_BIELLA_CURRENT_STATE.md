# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 72
  program_sha256: fcc927b86136f3547156d26cb1f8c1c9e9e27679d9b725cda53c13148600ad08
  task_program_authority: true
  production_execution_authority: true
  production_order_status_authority: true

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

repository:
  repository: UNKNOWN
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  source_identity_source: LIVE_GIT_READ_REQUIRED

active_execution:
  id: MINITZ-STARTUP-FOUNDATION-01
  task_revision: 1
  task_sha256: ca57e6973d62748ec646d328920b7cb10c620766b23b86446d3932fa60440b1c
  lane: Engine
  state: WORKING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

transition_receipt:
  predecessor_task_id: UNIFY-03
  predecessor_task_revision: 5
  predecessor_task_sha256: 9490672114da5b7cff9329fbf78a04ce27768982a4dd2191dd707cec29638d3f
  predecessor_program_revision: 60
  predecessor_program_sha256: 87abed8a842e10a735c2a30645310241b316aaf5b225e6d3181db9107c33a8fa
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 8b4985f54a56780b54131c63db75cc2f0180f09fcc6275cefcce8150de860d34

progress:
  completed_tasks: 22
  active_tasks: 14
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
