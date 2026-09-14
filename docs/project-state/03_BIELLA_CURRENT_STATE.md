# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 87
  program_sha256: cd0c9c70076fecbb1f37aab383a5c6eeb6341332d7d3aad56f0ff093c73edeef
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
  id: MINITZ-INSTALL-UPDATE-01
  task_revision: 1
  task_sha256: 7197ad0d3ec727301e06576219b7a85e075ff9e9b689f4583a89f9b7fb30cd82
  lane: Engine
  state: PENDING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

transition_receipt:
  predecessor_task_id: MINITZ-UX-OPS-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 11b835dfa5a28a39b0586ff0dfbc4f532e4465e170fb98473974284d0ae2ae64
  predecessor_program_revision: 86
  predecessor_program_sha256: cd2821faaa98f7259b280581488015d4de4890280a664b9ca4745fc72ba35155
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 623dc6941aedaee3507853201cf194e93bdd5936980e2f603a56a8abeac99519

progress:
  completed_tasks: 30
  active_tasks: 6
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
