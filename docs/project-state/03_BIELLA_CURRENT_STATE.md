# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 78
  program_sha256: 1ea12742563168211131d5961a5e0b0f9a2b2d644b0061632a0c982f2cc9f762
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
  id: MINITZ-AI-RUNTIME-01
  task_revision: 2
  task_sha256: a1a168d510654dfef32cac82419e2b32258b4f1c96db712dd55b399f84c262ef
  lane: Engine
  state: WORKING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-KNOWLEDGE-TRANSFER-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 728ed29dce666d31d4ff5706bc063e5a27a735849b9244e45ae9ed4cf69d46f1
  predecessor_program_revision: 76
  predecessor_program_sha256: 6a37d4e974dcc934812fd629d27c35f7ffd1af871e6c02d0307c15943074af03
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 160b9693ee8926f52a9509e4d222a33fff099b5457f4d05c44f3e3c9cdff874f

progress:
  completed_tasks: 25
  active_tasks: 11
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
