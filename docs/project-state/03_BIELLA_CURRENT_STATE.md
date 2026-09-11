# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 52
  program_sha256: 67be3611e10e3a79943fe600575a35dd472286b2c1ab22e7a86c2d6e4aec790d
  task_program_authority: true
  production_execution_authority: true
  production_order_status_authority: true

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

repository:
  repository: /root/biella/repos/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  source_identity_source: LIVE_GIT_READ_REQUIRED

active_execution:
  id: UNIFY-06
  task_revision: 5
  task_sha256: 0147f62c77f437ffd40953ddaff92504dbad81d8f2fedf772010d29933952623
  lane: Engine
  state: PENDING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

transition_receipt:
  predecessor_task_id: UNIFY-04
  predecessor_task_revision: 6
  predecessor_task_sha256: 87051b6d2ea4bdb3a721f47c41d4fd7ac7bff996676d2ef5aacdd5e0a87b5cf1
  predecessor_program_revision: 51
  predecessor_program_sha256: 00db40a9a09fc6e6a032ef53410d0a992a72103c493f04e02521ba7ddcc8e82f
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: f29c98bf68288aed5f1f4d7158615c4ae3fe16e4a41c5567929e4413c2acdbf0

progress:
  completed_tasks: 15
  active_tasks: 82
  total_tasks: 97

execution_invariants:
  one_task_program: true
  derived_ledgers_authority: false
  runner_and_auto_feeder_source: MINITZ_TASK_PROGRAM_ONLY
  hidden_task_queue_allowed: false
  generic_scheduler_progression_mutation: false
  publication_cursor_authority: false
  local_qwen_authority: false
```
