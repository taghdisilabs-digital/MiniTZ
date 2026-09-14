# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 79
  program_sha256: e26ad69d643837132d569405655791775e3d4defd63b6d7fa476d4b07c993deb
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
  id: MINITZ-CAPABILITIES-01
  task_revision: 1
  task_sha256: bb20a113d1448cba98d305d33b99428517ce8055b32bac3605dd2c91b9947190
  lane: Engine
  state: PENDING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-AI-RUNTIME-01
  predecessor_task_revision: 2
  predecessor_task_sha256: a1a168d510654dfef32cac82419e2b32258b4f1c96db712dd55b399f84c262ef
  predecessor_program_revision: 78
  predecessor_program_sha256: 1ea12742563168211131d5961a5e0b0f9a2b2d644b0061632a0c982f2cc9f762
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: ccace4af1118c20acebba6d333c59c6c038e29a02aadbf7ad4dc9e30fc380278

progress:
  completed_tasks: 26
  active_tasks: 10
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
