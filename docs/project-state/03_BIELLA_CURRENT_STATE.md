# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 86
  program_sha256: cd2821faaa98f7259b280581488015d4de4890280a664b9ca4745fc72ba35155
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
  id: MINITZ-UX-OPS-01
  task_revision: 2
  task_sha256: 11b835dfa5a28a39b0586ff0dfbc4f532e4465e170fb98473974284d0ae2ae64
  lane: Engine
  state: WORKING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-SECURITY-PRIVACY-01
  predecessor_task_revision: 2
  predecessor_task_sha256: aa0320996354ed4287b1c0dee49d4399760dd11194fd02c4a0252a1af383ab6c
  predecessor_program_revision: 84
  predecessor_program_sha256: 63e5a2bd6a34c98db3e89ca7738c745d08426a1900a260e56349b13e96d9b785
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 3f03171338ddee96b5ee5322f63fa35c5c221fe4a7556ba2a86cab34570fcf14

progress:
  completed_tasks: 29
  active_tasks: 7
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
