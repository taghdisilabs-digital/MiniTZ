# 04 - MINITZ ACTIVE TASK PROJECTION

```yaml
schema: minitz.active_task_projection/v1
projection_authority: false
task_program: /state/task-program/TASK_PROGRAM.json
program_id: MINITZ_REBORN_SINGLE_TASK_PROGRAM
program_revision: 103
program_sha256: 8cab9f4ab3527d1fa91bfd55a7de3012a1008721910a7a114c4450d0a08abd55

progression_family:
  id: MINITZ_PROGRESSION_FAMILY
  scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY
  progression_mutation: false

authority:
  progression: MINITZ_TASK_PROGRAM_ONLY
  derived_ledgers: NON_AUTHORITATIVE
  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM

task:
  id: NONE
  project: MiniTZ
  section: NONE
  class: NONE
  title: No active MiniTZ task
  status: COMPLETE
  runner: STOPPED

transition_receipt:
  predecessor_task_id: MINITZ-FINAL-CLOSURE-01
  predecessor_task_revision: 2
  predecessor_task_sha256: 647f0a29a212a351816d974f327aacc45d2e7ebff36cc6d5853c795347a95c0f
  predecessor_program_revision: 102
  predecessor_program_sha256: 8b592c1abcaa442a07da46848387eacee5ada453f6594c275321aa2496f2d499
  run_ref: NONE
  session_ref: NONE
  run_state_ref: NONE
  receipt_sha256: 1a9eee445ab576cf5f5671db9139c62e2ae205f0cbc6727463a7c7ddcfd60a79

stop: No active MiniTZ task; validate and persist before advancing.
```
