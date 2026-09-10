# 03 - MINITZ CURRENT STATE PROJECTION

```yaml
schema: minitz.current_state_projection/v1
state_class: VOLATILE_CURRENT
projection_authority: false

authority:
  progression_source: MINITZ_TASK_PROGRAM_ONLY
  task_program_path: /root/biella/analysis/live_audit/TASK_PROGRAM.json
  program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
  program_revision: 31
  program_sha256: 0761279a9bda1f16fee2a3d24f8a5b2f52b7054871a66b6716ebc8ce51f7d643
  task_program_authority: true
  production_execution_authority: true
  production_order_status_authority: true

repository:
  repository: taghdisilabs-digital/MiniTZ
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  source_identity_source: LIVE_GIT_READ_REQUIRED

active_execution:
  id: UNIFY-02
  task_revision: 5
  task_sha256: 8b84ce809c6aa10e349ac5aa7fb907be9479f1f7888e8866c321502c2191c47b
  lane: Engine
  state: PENDING
  runner: READY
  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json

progress:
  completed_tasks: 13
  active_tasks: 16
  total_tasks: 29

execution_invariants:
  one_task_program: true
  derived_ledgers_authority: false
  runner_and_auto_feeder_source: MINITZ_TASK_PROGRAM_ONLY
  hidden_task_queue_allowed: false
  publication_cursor_authority: false
  local_qwen_authority: false
```
