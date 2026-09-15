# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 96
program_sha256: dbb227888d2745eec7ff7cd47b78a4782955f9fb76b76240bf1078c4419f98d3

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

task:
  id: MINITZ-BOOTABLE-IMAGE-01
  project: MiniTZ
  section: minitz
  class: medium
  title: Build one bootable/installable MiniTZ OS Mother / Owner Version artifact from the canonical source
  status: WORKING
  runner: READY
  lane: Engine
  revision: 4
  task_sha256: ac02353555b069e178e697845b4f86e158b6aaa6acd72f9add19d8e18e6cbc91

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
