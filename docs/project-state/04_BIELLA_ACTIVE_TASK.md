# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /root/biella/analysis/live_audit/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 28
program_sha256: 31dbc703809e6d20cba15fe4cf398f0867a8ad0626a4613f1e403daf6c52b8e6

task:
  id: UNIFY-14
  project: MiniTZ
  section: minitz
  class: hard
  title: Converge active policy into MiniTZ-native semantic rule authority plus derived projections
  status: DEFERRED
  runner: READY
  lane: Engine
  revision: 8
  task_sha256: b6ef553e66d9d6dfb0db3bc66bf7580bcb0c6e27cf0731d63596cde9cc732f8f

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

stop: Execute only the current MiniTZ task UNIFY-14; validate and persist before advancing.
```
