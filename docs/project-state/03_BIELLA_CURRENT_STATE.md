# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 27
  program_sha256: 7169769f48ce705b16ed547ad103470cc98263e07c6dbac9e6e24557daa3fb35
  task_program_authority: true
  production_execution_authority: true
  production_order_status_authority: true

repository:
  repository: taghdisilabs-digital/MiniTZ
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  source_identity_source: LIVE_GIT_READ_REQUIRED

active_execution:
  id: UNIFY-01
  task_revision: 3
  task_sha256: 4fbced8b814df3e5a70f651bfc8509a52e6757df77c7a41ca1158fe6af5a621f
  lane: Engine
  state: PENDING
  runner: READY
  run_ref: commander-run://17ce7d66-d0dc-4592-b608-944e6682d2af/182617/UNIFY-01-r3
  session_ref: commander-session://17ce7d66-d0dc-4592-b608-944e6682d2af/182617
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

progress:
  completed_tasks: 11
  active_tasks: 18
  total_tasks: 29

execution_invariants:
  one_task_program: true
  derived_ledgers_authority: false
  runner_and_auto_feeder_source: MINITZ_TASK_PROGRAM_ONLY
  hidden_task_queue_allowed: false
  publication_cursor_authority: false
  local_qwen_authority: false
```
