# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 28
  program_sha256: 31dbc703809e6d20cba15fe4cf398f0867a8ad0626a4613f1e403daf6c52b8e6
  task_program_authority: true
  production_execution_authority: true
  production_order_status_authority: true

repository:
  repository: taghdisilabs-digital/MiniTZ
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  source_identity_source: LIVE_GIT_READ_REQUIRED

active_execution:
  id: UNIFY-14
  task_revision: 8
  task_sha256: b6ef553e66d9d6dfb0db3bc66bf7580bcb0c6e27cf0731d63596cde9cc732f8f
  lane: Engine
  state: DEFERRED
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

progress:
  completed_tasks: 12
  active_tasks: 17
  total_tasks: 29

execution_invariants:
  one_task_program: true
  derived_ledgers_authority: false
  runner_and_auto_feeder_source: MINITZ_TASK_PROGRAM_ONLY
  hidden_task_queue_allowed: false
  publication_cursor_authority: false
  local_qwen_authority: false
```
