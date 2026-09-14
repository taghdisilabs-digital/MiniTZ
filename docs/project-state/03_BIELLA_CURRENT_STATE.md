# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 84
  program_sha256: 63e5a2bd6a34c98db3e89ca7738c745d08426a1900a260e56349b13e96d9b785
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
  id: MINITZ-SECURITY-PRIVACY-01
  task_revision: 2
  task_sha256: aa0320996354ed4287b1c0dee49d4399760dd11194fd02c4a0252a1af383ab6c
  lane: Engine
  state: WORKING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-BROWSER-HUMAN-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 5e3a935674dc09b983801f7332412d56d54bfa9292cc82cb0420f1b9306d2d04
  predecessor_program_revision: 82
  predecessor_program_sha256: 9cb53b3c276c220ca8d03017fe6f853438007a3f6946ff11777c52e849c012fc
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 65244da93f1beb65a0e12dc6092879bf81fca3ab3a409079439f6b50bfffa60a

progress:
  completed_tasks: 28
  active_tasks: 8
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
