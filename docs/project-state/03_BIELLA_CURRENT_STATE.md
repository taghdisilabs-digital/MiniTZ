# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 82
  program_sha256: 9cb53b3c276c220ca8d03017fe6f853438007a3f6946ff11777c52e849c012fc
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
  id: MINITZ-BROWSER-HUMAN-01
  task_revision: 2
  task_sha256: 5e3a935674dc09b983801f7332412d56d54bfa9292cc82cb0420f1b9306d2d04
  lane: Engine
  state: WORKING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-CAPABILITIES-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 67caa666b612a9381e1a6a4bc3b7f1ece837171d49a6ab7d3b88a503d953da1b
  predecessor_program_revision: 80
  predecessor_program_sha256: a0e18b284ef3cdb338c1e59bb84b59091955da6423f07dd4019dd4286c301ad0
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 6f86caec1ed07582f5228eff1f9f96f21cbe089ab1bc0063e6d984f0466a297b

progress:
  completed_tasks: 27
  active_tasks: 9
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
