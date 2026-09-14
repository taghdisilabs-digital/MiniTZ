# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 93
program_sha256: 7286431027836dbcdf8a556fd2f4d92c5374bdded63da9c61a6aab10e2195be9

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-BOOTABLE-IMAGE-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Build one bootable installable MiniTZ OS artifact from the canonical source
  status: PENDING
  runner: READY
  lane: Engine
  revision: 1
  task_sha256: c733b5f30e3af54fe65a9d615392c7dd189a2eed5b878b4a6e8e8a019d7a5b58

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

transition_receipt:
  predecessor_task_id: MINITZ-GITHUB-MAIN-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 889fcb4e98bb0b8186e044f2305467f7c9b8671f3448e70f5c46212db7e4871b
  predecessor_program_revision: 92
  predecessor_program_sha256: 9294c91b7ad866c403e96c87907c5dd047ce837b280be7384a360c948c2efa44
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 32c8d32e03970d2841503dad769b8c4a7161e56a8fd4292bc6dbc2cd5109d667

stop: Execute only the current MiniTZ task MINITZ-BOOTABLE-IMAGE-01; validate and persist before advancing.
```
