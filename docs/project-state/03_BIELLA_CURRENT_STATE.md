# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 36
  program_sha256: 6e5d95e12196842e7d23bc88c4914db816312855835cedad1227ad30a8eff9ff
  task_program_authority: true
  production_execution_authority: true
  production_order_status_authority: true

repository:
  repository: taghdisilabs-digital/MiniTZ
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  source_identity_source: LIVE_GIT_READ_REQUIRED

active_execution:
  id: UNIFY-03
  task_revision: 5
  task_sha256: 6e0daf1219d34718f2e1fa3b5b74ebb001f705687f3592879e2b1def78df3597
  lane: Engine
  state: PENDING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

progress:
  completed_tasks: 14
  active_tasks: 749
  total_tasks: 763

execution_invariants:
  one_task_program: true
  derived_ledgers_authority: false
  runner_and_auto_feeder_source: MINITZ_TASK_PROGRAM_ONLY
  hidden_task_queue_allowed: false
  publication_cursor_authority: false
  local_qwen_authority: false
```
